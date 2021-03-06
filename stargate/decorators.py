"""View Function decorators. Each view function (get, post, patch, delete) gets decorated with these functions. For more details 
please check comments of individual function.

"""

import re
from functools import wraps
from flask import request, json, jsonify
from .exception import NotAcceptable, MediaTypeNotSupported, ProcessingException, ConflictException, ValidationError
from werkzeug import parse_options_header
from .const import MediatypeConstants

"""View function Content-Type decorators"""
def requires_api_accept(func):
    @wraps(func)
    def new_func(*args, **kw):
        header = request.headers.get('Accept')
        if header is None:
            return func(*args, **kw)
        header_pairs = list(parse_accept_header(header))
        if len(header_pairs) == 0:
            return func(*args, **kw)
        jsonapi_pairs = [(name, extra) for name, extra in header_pairs
                         if name.startswith(MediatypeConstants.CONTENT_TYPE)]
        if len(jsonapi_pairs) == 0:
            detail = ('Accept header, if specified, must be the JSON API media type: {0}'.format(MediatypeConstants.CONTENT_TYPE))
            raise NotAcceptable(msg=detail)
        if all(extra is not None for name, extra in jsonapi_pairs):
            detail = ('Accept header contained API content type, but each'
                      ' instance occurred with media type parameters; at least'
                      ' one instance must appear without parameters')
            raise NotAcceptable(msg=detail)
        return func(*args, **kw)
    return new_func


def requires_api_mimetype(func):
    @wraps(func)
    def new_func(*args, **kw):
        if request.method not in ('PATCH', 'POST'):
            return func(*args, **kw)
        header = request.headers.get('Content-Type')
        content_type, extra = parse_options_header(header)
        content_is_json = content_type.startswith(MediatypeConstants.CONTENT_TYPE)
        if not content_is_json:
            detail = ('Request must have "Content-Type: {0}"'
                      ' header').format(MediatypeConstants.CONTENT_TYPE)
            raise MediaTypeNotSupported(msg=detail)
        if extra:
            detail = ('Content-Type header must not have any media type'
                      ' parameters but found {0}'.format(extra))
            raise MediaTypeNotSupported(msg=detail)
        return func(*args, **kw)
    return new_func

def parse_accept_header(value):
    def match_to_pair(match):
        name = match.group(1)
        extra = match.group(2)
        quality = max(min(float(extra), 1), 0) if extra else None
        return name, quality
    return map(match_to_pair, MediatypeConstants.ACCEPT_RE.finditer(value))

CONFLICT_INDICATORS = ('conflicts with', 'UNIQUE constraint failed',
                        'is not unique')

"""View Function Error handling Decorators"""
def catch_processing_exceptions(func):
    @wraps(func)
    def new_func(*args, **kw):
        try:
            return func(*args, **kw)
        except ProcessingException as exception:
            raise ProcessingException(exception)
    return new_func

def catch_integrity_errors(session):
    def decorated(func):
        @wraps(func)
        def wrapped(*args, **kw):
            try:
                return func(*args, **kw)
            except SQLAlchemyError as exception:
                session.rollback()
                exception_string = str(exception)
                if any(s in exception_string for s in CONFLICT_INDICATORS):
                    raise ConflictException(exception_string)
                else:
                    raise ValidationError(exception_string)
            return wrapped
        return decorated
