import re
from mimerender import FlaskMimeRender
from mimerender import register_mime
from itertools import chain
from functools import wraps
from werkzeug.exceptions import HTTPException
from flask.views import MethodView
from flask import request, json, jsonify, current_app
from ..broker import collection_name
from collections import defaultdict
from sqlalchemy.exc import SQLAlchemyError
from .query_helper.search import Search
from .query_helper.pagination import SimplePagination
from sqlalchemy.orm.query import Query


FILTER_PARAM = 'filter[objects]'
SORT_PARAM = 'sort'
GROUP_PARAM = 'group'
PAGE_NUMBER_PARAM = 'page[number]'
PAGE_SIZE_PARAM = 'page[size]'
SINGLE_RESOURCE_PARAM = 'filter[single]'

chain = chain.from_iterable


"""Utility functions"""
def upper_keys(dictionary):
    return dict((k.upper(), v) for k, v in dictionary.items())

def parse_sparse_fields(type_=None):
        fields = dict((key[7:-1], set(value.split(',')))
                  for key, value in request.args.items()
                  if key.startswith('fields[') and key.endswith(']'))
        return fields.get(type_) if type_ is not None else fields
#######################################################################################################

class BaseAPI(MethodView):
    
    decorators = [  
                    requires_json_api_accept, 
                    requires_json_api_mimetype,
                    mimerender,
                    catch_processing_exceptions
                 ]
    def __init__(self, session, model, preprocessors=None, postprocessors=None,
                 primary_key=None, serializer=None, deserializer=None,
                 validation_exceptions=None, includes=None, page_size=10,
                 max_page_size=100, allow_to_many_replacement=False, *args,
                 **kw):

        super(BaseAPI, self).__init__(*args, **kw)

        self.collection_name = collection_name(model)
        
        self.default_includes = includes
        if self.default_includes is not None:
            self.default_includes = frozenset(self.default_includes)

        self.session = session
        self.model = model

        self.allow_to_many_replacement = allow_to_many_replacement

        self.page_size = page_size

        self.max_page_size = max_page_size

        self.serialize = serializer

        self.deserialize = deserializer

        self.validation_exceptions = tuple(validation_exceptions or ())

        self.primary_key = primary_key

        self.postprocessors = defaultdict(list, upper_keys(postprocessors or {}))

        self.preprocessors = defaultdict(list, upper_keys(preprocessors or {}))

        self.sparse_fields = parse_sparse_fields()

        decorate = lambda name, f: setattr(self, name, f(getattr(self, name)))
        for method in ['get', 'post', 'patch', 'delete']:
            if hasattr(self, method):
                decorate(method, catch_integrity_errors(self.session))
   
    def get_all_inclusions(self, instance_or_instances):
        if isinstance(instance_or_instances, Query):
            to_include = set(chain(self.resources_to_include(resource)
                                   for resource in instance_or_instances))
        else:
            to_include = self.resources_to_include(instance_or_instances)
        return self._serialize_many(to_include)
    
    def _serialize_many(self, instances, relationship=False):
        result = []
        failed = []
        for instance in instances:
            model = get_model(instance)
            if relationship:
                serialize = self.serialize_relationship
            else:
                try:
                    serialize = serializer_for(model)
                except ValueError:
                    serialize = self.serialize
            _type = collection_name(model)
            only = self.sparse_fields.get(_type)
            try:
                serialized = serialize(instance, only=only)
                result.append(serialized)
            except SerializationException as exception:
                failed.append(exception)
        if failed:
            raise MultipleExceptions(failed)
        return result
    
    def resources_to_include(self, instance):
        toinclude = request.args.get('include')
        if toinclude is None and self.default_includes is None:
            return {}
        elif toinclude is None and self.default_includes is not None:
            toinclude = self.default_includes
        else:
            toinclude = set(toinclude.split(','))
        return set(chain(resources_from_path(instance, path)
                         for path in toinclude))

    def _collection_filter_parameters(self):
        filters = json.loads(request.args.get(FILTER_PARAM, '[]'))
        sort = request.args.get(SORT_PARAM)
        if sort:
            sort = [('-', value[1:]) if value.startswith('-') else ('+', value)
                    for value in sort.split(',')]
        else:
            sort = []

        group_by = request.args.get(GROUP_PARAM)
        if group_by:
            group_by = group_by.split(',')
        else:
            group_by = []

        try:
            single = bool(int(request.args.get(SINGLE_RESOURCE_PARAM, 0)))
        except ValueError:
            raise SingleKeyError('failed to extract Boolean from parameter')

        return filters, sort, group_by, single

    
    def _get_collection(self,filters=None, sort=None, group_by=None,
                               single=False):
        try:
            search_items = Search(self.session, self.model, filters=filters, sort=sort,
                                   group_by=group_by)
        except ComparisonToNull as exception:
            detail = str(exception)
            return error_response(400, cause=exception, detail=detail)
        except UnknownField as exception:
            detail = 'Invalid filter object: No such field "{0}"'
            detail = detail.format(exception.field)
            return error_response(400, cause=exception, detail=detail)
        except Exception as exception:
            detail = 'Unable to construct query'
            return error_response(400, cause=exception, detail=detail)

        #collection
        if not single:
            try:
                paginated = SimplePagination.simple_pagination(search_items.search_collection(),filters = filters, sort = sort, group_by = group_by)
            except MultipleExceptions as e:
                return errors_from_serialization_exceptions(e.exceptions)
            except PaginationError as exception:
                detail = exception.args[0]
                return error_response(400, cause = exception, detail = detail)
            
            data = paginated.items
            links = paginated.pagination_links
            header = ','.join(paginated.header_links)
            link_header = dict(Link = link_header)
            num_results = paginated.num_results
            single = single
        
        #Force single
        else:
            try:
                data = search_items.search_collection().one()
            except NoResultFound as exception:
                detail = 'No result found'
                return error_response(404, cause=exception, detail=detail)
            except MultipleResultsFound as exception:
                detail = 'Multiple results found'
                return error_response(404, cause=exception, detail=detail)
            only = self.sparse_fields.get(self.collection_name)
            try:
                serialize = self.serialize
                result['data'] = serialize(data, only=only)
            except SerializationException as exception:
                return errors_from_serialization_exceptions([exception])
            
            #Link Header Generation
            primary_key = primary_key_for(data)
            pk_value = result['data'][primary_key]
            url = '{0}/{1}'.format(request.base_url, pk_value)
            headers = dict(Location=url)

            link_header = headers
            single = single

        try:
            included = self.get_all_inclusions(search_items)
        except MultipleExceptions as e:
            return errors_from_serialization_exceptions(e.exceptions,
                                                        included=True)
        if included:
            inclusions = included

        result = {'data': data, 'link_header': link_header, 'links': links, 'num_results': num_results,'include': inclusions, 'single': 'single'}
        
        for postprocessor in self.postprocessors['GET_COLLECTION']:
            postprocessor(result=result, filters=filters, sort=sort,
                          group_by=group_by, single=single)
        return result
