import re
import os
import base64

from .message import HTTPHeaders
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
    def by_semicolon_equal_pairs(value, key_case_insensitive = True):
        """
            [Format] <key>=<value>; <key>; ...
            [Example Value] multipart/form-data; boundary=327c6dfd4efcbc1a8cb73dfbd452c924
            [Return] dict: {key: value, key: None, ...}
        """
        pairs_splited = value.split(';')
        dict = {}
        for pair in pairs_splited:
            pair = pair.strip()
            pair_splited = pair.split('=', 1)
            if len(pair_splited) == 2:
                key, value = pair_splited
                key = key.lower() if key_case_insensitive else key
                dict[key.strip()] = value.strip()
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


class HTTPBodyUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def parse_multipart_form_data(body, boundary): # data, boundary are bytes
        """
            [Example Value]
                --327c6dfd4efcbc1a8cb73dfbd452c924
                Content-Disposition: form-data; name="file1"; filename="example.txt"
                Content-Type: text/plain
                
                Content of file 1
                --327c6dfd4efcbc1a8cb73dfbd452c924
                Content-Disposition: form-data; name="file2"; filename="example2.txt"
                Content-Type: text/plain
                
                Content of file 2
                --327c6dfd4efcbc1a8cb73dfbd452c924--
            [Return] file_list: [{name: str, filename: str, content_type: str, content: bytes}), ...], [] if no file, None if error
                (the four items may not exist)
        """
        if not isinstance(body, bytes):
            body = body.encode()
        if not isinstance(boundary, bytes):
            boundary = boundary.encode()
        
        file_list = []
        parts = body.split(b'--' + boundary)
        if len(parts) < 3:
            return None
        for part in parts[1:-1]: # ignore '' and '--\r\n' at the beginning and end
            part = part[2:-2] # remove \r\n at the beginning and end
            part_splited = part.split(b'\r\n\r\n', 1)
            if len(part_splited) != 2:
                # return None
                continue
            
            header = HTTPHeaders.from_parsing(part_splited[0])
            content = part_splited[1]
            
            file_item = {}
            if header.get('Content-Disposition'):
                content_disposition_dict = HTTPHeaderUtils.by_semicolon_equal_pairs(header.get('Content-Disposition'))
                if content_disposition_dict.get('name', None):
                    file_item['name'] = content_disposition_dict['name'].strip('"').strip("'")
                if content_disposition_dict.get('filename', None):
                    file_item['filename'] = content_disposition_dict['filename'].strip('"').strip("'")
                if header.get('Content-Type'):
                    file_item['content_type'] = header.get('Content-Type')
                file_item['content'] = content
            file_list.append(file_item)
        
        return file_list

