import re
import os
import base64
import mimetypes

from .message import HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from .exception import HTTPStatusException


class HTMLUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def render_template(template, variables = {}, pattern = r'{{\s*([^{}]+)\s*}}'): # r'{{\s*([^{}|]+)\s*(?:\|\s*safe\s*)?}}'
        def replace(match):
            variable = match.group(1).strip()
            return str(variables.get(variable, f'{{{{ {variable} }}}}'))
        
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
            try:
                up_splited = base64.b64decode(splited[1]).decode().split(':')
            except Exception:
                raise HTTPStatusException(400) # base64 decoding error
            if len(up_splited) == 2:
                return tuple(up_splited)
            else:
                raise HTTPStatusException(400)
        else:
            return (None, None)
    
    @staticmethod
    def by_semicolon_equal_pairs(value):
        """
            [Format] <key>=<value>; <key>; ...
            [Example Value] multipart/form-data; boundary=327c6dfd4efcbc1a8cb73dfbd452c924
            [Return] dict: {key: value, key: None, ...}
        """
        pairs_splited = value.split(';')
        dict = {}
        for pair in pairs_splited:
            pair = pair.strip()
            pair_splited = pair.split('=')
            if len(pair_splited) == 2:
                key, value = pair_splited
                dict[key.strip().lower()] = value.strip() # case-insensitive key
            elif len(pair_splited) == 1:
                key = pair_splited[0]
                dict[key] = None
            elif len(pair) != 0:
                raise HTTPStatusException(400)
        return dict
    
    @staticmethod
    def parse_cookie(value):
        """
            [Format] Cookie: <cookie-name>=<cookie-value>; ...
            [Example Value] session-id=e53fc18600f64ec64c36b550a68fbe5a; __itrace_wid=34a8a195-5ac4-4503-3736-6cc89e8e02fc
            [Return] cookie_dict
        """
        return HTTPHeaderUtils.by_semicolon_equal_pairs(value)
    
    @staticmethod
    def parse_content_type(value):
        """
            [Format] Content-Type: <type>/<subtype>; boundary=<boundary> TODO: 看文档还有什么
            [Example Value] multipart/form-data; boundary=327c6dfd4efcbc1a8cb73dfbd452c924
            [Return] content_type_dict
        """
        return HTTPHeaderUtils.by_semicolon_equal_pairs(value)


class HTTPResponseGenerator:
    def __init__(self):
        pass
    
    @staticmethod
    def by_content_type(body = b'', content_type = 'text/plain', version = 'HTTP/1.1', status_code = 200, status_desc = 'OK', extend_headers = {}):
        if not isinstance(body, bytes):
            body = body.encode()
        return HTTPResponseMessage(
            HTTPStatusLine(version, status_code, status_desc),
            HTTPHeaders({
                'Content-Type': content_type,
                'Content-Length': str(len(body)),
                **extend_headers
            }),
            body
        )
    
    @staticmethod
    def by_file_path(file_path, use_mime = True, version = 'HTTP/1.1', status_code = 200, status_desc = 'OK', extend_headers = {}):
        with open(file_path, 'rb') as f:
            body = f.read()
        if use_mime:
            content_type = mimetypes.guess_type(file_path)[0]
            content_disposition = 'inline'
        else:
            content_type = 'application/octet-stream'
            content_disposition = 'attachment'
        return HTTPResponseMessage(
            HTTPStatusLine(version, status_code, status_desc),
            HTTPHeaders({
                'Content-Type': content_type,
                'Content-Length': str(len(body)),
                'Content-Disposition': f'{content_disposition}; filename="{os.path.basename(file_path)}"',
                **extend_headers
            }),
            body
        )

