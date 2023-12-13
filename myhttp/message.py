import mimetypes
import re
import os

from .exception import HTTPStatusException


class HTTPUrl:
    path_pattern = re.compile(r'^/?([^?]*)(\?.*)?$') # separate path and params
    params_pattern = re.compile(r'[\?&]([^=]+)=([^&]*)') # param key-value pairs
    percent_encoding_pattern = re.compile(r'%([0-9a-fA-F]{2})') # percent encoding
    
    def __init__(self, path_list = [''], params = {}):
        self.path_list = path_list # the last item is the file name, if path_list[-1] == '' means directory
        self.params = params
    
    # def serialize(self):
    #     # TODO: 对特殊字符进行 % 编码
    #     return '/' + '/'.join(self.path_list) + '?' + '&'.join([f'{key}={value}' for key, value in self.params.items()])
    
    @classmethod
    def from_parsing(c, url):
        # decode percent encoding
            # TODO: 若带有 #, 浏览器会自动去除 # 后的内容，无法解决，除非修改文档 API，在此记录一下
            # 同样的，在 get params 中带有 & 和 = 也会无法正确解析
        decoded_url = c.percent_encoding_pattern.sub(lambda x: chr(int(x.group(1), 16)), url)
        decoded_url = decoded_url.encode('ISO-8859-1').decode('utf-8')
        
        path_match = c.path_pattern.match(decoded_url)
        if path_match:
            path = path_match.group(1)
            path_list = path.split('/') # [segment for segment in path.split('/') if segment]
            
            params_str = path_match.group(2)
            params_dict = dict(c.params_pattern.findall(params_str)) if params_str else {}
            
            return c(path_list, params_dict)
        else:
            raise HTTPStatusException(400) # TODO: URL parse error -> Bad Request?


class HTTPRequestLine:
    def __init__(self, method, path, version):
        self.method = method
        self.path = path
        self.version = version
    
    def serialize(self):
        return f'{self.method} {self.path} {self.version}\r\n'.encode()
    
    @classmethod
    def from_parsing(c, line):
        # e.g. b'GET / HTTP/1.1'
        splitted = line.decode().split(' ')
        if len(splitted) != 3:
            raise HTTPStatusException(400)
        return c(splitted[0], splitted[1], splitted[2])


class HTTPStatusLine:
    def __init__(self, version, status_code, status_desc):
        self.version = version
        self.status_code = status_code
        self.status_desc = status_desc
    
    def serialize(self):
        return f'{self.version} {self.status_code} {self.status_desc}\r\n'.encode()
    
    @classmethod
    def from_parsing(c, line):
        # e.g. b'HTTP/1.1 200 OK'
        splitted = line.decode().split(' ')
        try:
            stat_code = int(splitted[1])
        except ValueError:
            raise HTTPStatusException(400)
        return c(splitted[0], stat_code, splitted[2])


class HTTPHeaders:
    def __init__(self, headers = {}):
        headers_lower = {key.lower(): value for key, value in headers.items()} # key is case-insensitive
        self.headers: dict = headers_lower
    
    def is_exist(self, key):
        # key is case-insensitive
        key_lower = key.lower()
        return key_lower in self.headers
    
    def get(self, key):
        # key is case-insensitive
        key_lower = key.lower()
        return self.headers.get(key_lower, None)

    def set(self, key, value):
        # key is case-insensitive
        key_lower = key.lower()
        self.headers[key_lower] = value
    
    def remove(self, key):
        # key is case-insensitive
        key_lower = key.lower()
        if self.headers.__contains__(key_lower):
            del self.headers[key_lower]
    
    def clear(self):
        self.headers.clear()
    
    def serialize(self):
        return ''.join([f'{key}: {value}\r\n' for key, value in self.headers.items()]).encode()
    
    @classmethod
    def from_parsing(c, lines):
        headers = {}
        splitted = lines.split(b'\r\n')
        for line in splitted:
            splitted = line.decode().split(':', 1) # TODO: value may contain ':', or use rsplit(': ')?
            if len(splitted) == 2:
                # key is case-insensitive, value is not certain
                key_lower = splitted[0].lower().strip()
                value = splitted[1].strip()
                headers[key_lower] = value
            elif len(line) != 0:
                raise HTTPStatusException(400)
        return c(headers)


class HTTPRequestMessage:
    def __init__(self, request_line, headers, body = b''):
        self.request_line = request_line
        self.headers = headers
        self.body = body
        self.headers.set('Content-Length', len(body))
    
    def serialize(self):
        return self.request_line.serialize() + self.headers.serialize() + b'\r\n' + self.body


class HTTPResponseMessage:
    def __init__(self, status_line, headers, body = b''):
        self.status_line = status_line
        self.headers = headers
        self.body = body
    
    def update_version(self, version):
        self.status_line.version = version
    
    def update_status(self, code, desc = None):
        if not desc:
            desc = HTTPStatusException.default_status_description[code]
        self.status_line.status_code = code
        self.status_line.status_desc = desc
    
    def update_header(self, key, value):
        self.headers.set(key, value)
    
    def update_headers(self, headers):
        for key, value in headers.items():
            self.headers.set(key, value)
    
    def update_body(self, body): # automatically set Content-Length if there has been one; TODO: chunked 不走这
        if not isinstance(body, bytes):
            body = body.encode()
        if self.headers.is_exist('Content-Length'):
            self.headers.set('Content-Length', len(body))
        self.body = body
        
    def serialize_header(self):
        return self.status_line.serialize() + self.headers.serialize() + b'\r\n'
    
    def serialize(self):
        return self.serialize_header() + self.body
    
    """
        Generating
    """
    
    def update_by_content_type(self, body = b'', content_type = 'text/plain'):
        if not isinstance(body, bytes):
            body = body.encode()
        
        self.update_header('Content-Type', content_type)
        self.update_header('Content-Length', str(len(body)))
        self.update_body(body)
    
    def update_by_file_path(self, file_path, use_mime = True):
        with open(file_path, 'rb') as f:
            body = f.read()
        if use_mime:
            content_type = mimetypes.guess_type(file_path)[0]
            content_disposition = 'inline'
        else:
            content_type = 'application/octet-stream'
            content_disposition = 'attachment'
        
        self.update_header('Content-Type', content_type)
        self.update_header('Content-Length', str(len(body)))
        self.update_header('Content-Disposition', f'{content_disposition}; filename="{os.path.basename(file_path)}"')
        self.update_body(body)
    
    @classmethod
    def from_parsing(c, data):
        headerlines, body = data.split(b'\r\n\r\n')
        splited = headerlines.split(b'\r\n')
        status_line, headers = splited[0], b'\r\n'.join(splited[1:])
        status_line = HTTPStatusLine.from_parsing(status_line)
        headers = HTTPHeaders.from_parsing(headers)
        return c(status_line, headers, body)