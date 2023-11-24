import re
import base64

from .message import HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from .exception import HTTPStatusException


class HTMLUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def render_template(template, variables = {}, pattern = r'{{\s*([^{}|]+)\s*(?:\|\s*safe\s*)?}}'):
        def replace(match):
            variable = match.group(1).strip()
            
            value = variables.get(variable, f'{{{{ {variable} }}}}')
            is_safe = '|safe' in match.group(0)
            if is_safe:
                value = str(value)
            
            return value
        
        pattern_compiled = re.compile(pattern)
        return pattern_compiled.sub(replace, template)


class HTTPHeaderUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def parse_authorization(value):
        # e.g. Basic MTIxMTAxMDQ6MTIzNDU2, return (username, decrypted password)
        splited = value.split(' ')
        if splited[0] == 'Basic':
            up_splited = base64.b64decode(splited[1]).decode().split(':')
            if len(up_splited) == 2:
                return tuple(up_splited)
            else:
                raise HTTPStatusException(400)
        else:
            raise HTTPStatusException(400)
    
    @staticmethod
    def parse_cookie(value):
        # e.g. session-id=[id]
        splited = value.split('=')
        if splited[0] == 'session-id':
            return splited[1]
        else:
            raise HTTPStatusException(400)


class HTTPResponseGenerator:
    def __init__(self):
        pass
    
    @staticmethod
    def text_html(body = '', version = 'HTTP/1.1', status_code = 200, status_desc = 'OK', extend_headers = {}):
        return HTTPResponseMessage(
            HTTPStatusLine(version, status_code, status_desc),
            HTTPHeaders({
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Length': str(len(body)),
                **extend_headers
            }),
            body.encode()
        )

