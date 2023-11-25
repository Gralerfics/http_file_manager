import re
import os
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


class KeyUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def random_key(half_length = 16, hex = True, not_in = None):
        key = os.urandom(half_length)
        key = key.hex() if hex else key
        if hasattr(not_in, '__contains__'):
            while key in not_in:
                key = os.urandom(half_length)
                key = key.hex() if hex else key
        return key


class HTTPHeaderUtils:
    # TODO: 这里的 400 都要慎重！有些浏览器发的标头千奇百怪，不能不支持就直接 400。
    def __init__(self):
        pass
    
    @staticmethod
    def parse_authorization_basic(value):
        """
            [Format] Authorization: <type> <credentials>
            [Example Value] Basic MTIxMTAxMDQ6MTIzNDU2
            [Return] (username, decrypted password)
        """
        splited = value.split(' ')
        if splited[0].lower() == 'basic':
            up_splited = base64.b64decode(splited[1]).decode().split(':')
            if len(up_splited) == 2:
                return tuple(up_splited)
            else:
                raise HTTPStatusException(400)
        else:
            return (None, None)
    
    @staticmethod
    def parse_cookie(value):
        """
            [Format] Cookie: <cookie-name>=<cookie-value>; ...
            [Example Value] session-id=e53fc18600f64ec64c36b550a68fbe5a; __itrace_wid=34a8a195-5ac4-4503-3736-6cc89e8e02fc
            [Return] cookie_dict
        """
        pairs_splited = value.split(';')
        cookies = {}
        for pair in pairs_splited:
            pair = pair.strip()
            pair_splited = pair.split('=')
            if len(pair_splited) == 2:
                key, value = pair_splited
                cookies[key.strip().lower()] = value.strip() # case-insensitive key
            elif len(pair) != 0:
                raise HTTPStatusException(400)
        return cookies
    
    @staticmethod
    def parse_content_type(value):
        """
            [Format] Content-Type: <type>/<subtype>; boundary=<boundary> TODO: 看文档还有什么
            [Example Value] multipart/form-data; boundary=327c6dfd4efcbc1a8cb73dfbd452c924
            [Return] TODO
        """
        pass


class HTTPResponseGenerator:
    def __init__(self):
        pass
    
    @staticmethod
    def text_plain(body = '', version = 'HTTP/1.1', status_code = 200, status_desc = 'OK', extend_headers = {}):
        return HTTPResponseMessage(
            HTTPStatusLine(version, status_code, status_desc),
            HTTPHeaders({
                'Content-Type': 'text/plain; charset=utf-8',
                'Content-Length': str(len(body)),
                **extend_headers
            }),
            body.encode()
        )
    
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

