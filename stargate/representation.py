from flask import request, make_response, jsonify, json
from .proxy import manager_info, URL_FOR, SERIALIZER_FOR
from .utils import get_paginated_url, get_pagination_links

class Representation():
        
    _response_message = {200: 'Ok.', 201: "Created"}

    def __init__(self, code, message = None, content_type=None, headers={}):
        
        self.__base_repr__ = {'meta':{'status_code':None, 'message':None, '_HEADERS':{'Content-Type':'application/json'}}}
        self.__base_repr__['meta']['status_code'] = code
        self.__base_repr__['meta']['message'] = self._response_message[code] if message is None else message
        self.__base_repr__['meta']['_HEADERS'].update(headers)

    def to_response(self):
        
        headers = self.__base_repr__['meta'].pop('_HEADERS', {}) if 'meta' in self.__base_repr__ else {}
        
        settings = {}
        settings.setdefault('indent', 4)
        settings.setdefault('sort_keys', True)
        
        response_doc = json.dumps(self.__base_repr__, **settings)
        response = make_response(response_doc)
        
        if headers:
            for key, value in headers.items():
                response.headers.set(key, value)
        return response

class InstanceRepresentation(Representation):
    
    def __init__(self, model, pk_id, data, *args, **kw):
        
        super(InstanceRepresentation, self).__init__(*args, **kw)
        self.model = model
        self.pk_id = pk_id
        self.data = data

    def to_response(self):

        self_link = manager_info(URL_FOR, self.model, pk_id = self.pk_id)
        
        self.__base_repr__['meta']['_HEADERS']['rel'] = self_link
        self.__base_repr__['data'] = self.data
        return super(InstanceRepresentation,self).to_response()
               

class CollectionRepresentation(Representation):
    
    def __init__(self, model, data, *args, **kw):
        
        super(CollectionRepresentation, self).__init__(*args, **kw)
        self.data = data
        self.model = model

    def to_response(self, page_size = None, page_number = None, pagination = None):
        
        self_link =  manager_info(URL_FOR, self.model)
        
        if pagination is not None and page_number is not None and page_size is not None:
            num_results = pagination.total
            first = 1
            last = pagination.pages
            prev = pagination.prev_num
            next = pagination.next_num
            page_size = page_size
            page_number = page_number
        
            self_link = get_paginated_url(self_link, page_number, page_size)
            self.__base_repr__['num_results'] = num_results
            self.__base_repr__['links'] = get_pagination_links(page_size, page_number, num_results, first, last, next, prev)
        
        self.__base_repr__['meta']['_HEADERS']['rel'] = self_link
        self.__base_repr__['data'] = self.data
        
        return super(CollectionRepresentation,self).to_response()
