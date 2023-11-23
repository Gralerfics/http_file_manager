import re
from .exception import HTTPStatusException


class URL:
    path_pattern = re.compile(r'/([^/?]+)')
    params_pattern = re.compile(r'\?([^/]+)')
    
    def __init__(self, path_list = [], params = {}):
        self.path_list = path_list
        self.params = params
    
    def serialize(self):
        return '/' + '/'.join(self.path_list) + '?' + '&'.join([f'{key}={value}' for key, value in self.params.items()])
    
    @classmethod
    def from_parsing(c, url):
        path_matches = c.path_pattern.findall(url)
        params_match = c.params_pattern.search(url)

        if params_match:
            params_string = params_match.group(1)
            params_list = params_string.split('&')
            get_params = {param.split('=')[0]: param.split('=')[1] for param in params_list}
        else:
            get_params = {}

        return c(path_matches, get_params)


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
        splitted = line.decode('utf-8').split(' ')
        try:
            stat_code = int(splitted[1])
        except ValueError:
            raise HTTPStatusException(400)
        return c(splitted[0], stat_code, splitted[2])


class HTTPHeaders:
    def __init__(self, headers = {}):
        self.headers: dict = headers
    
    def serialize(self):
        return ''.join([f'{key}: {value}\r\n' for key, value in self.headers.items()]).encode()
    
    @classmethod
    def from_parsing(c, lines):
        # TODO: 是否会有重复的标头 key？应该没有吧。
        headers = {}
        splitted = lines.split(b'\r\n')
        for line in splitted:
            splitted = line.decode('utf-8').split(': ')
            if len(splitted) == 2:
                headers[splitted[0]] = splitted[1]
            elif len(line) != 0:
                raise HTTPStatusException(400)
        return c(headers)


class HTTPRequestMessage:
    def __init__(self, request_line, headers, body = b''):
        self.request_line = request_line
        self.headers = headers
        self.body = body
    
    def serialize(self):
        return self.request_line.serialize() + self.headers.serialize() + b'\r\n' + self.body


class HTTPResponseMessage:
    def __init__(self, status_line, headers, body = b''):
        self.status_line = status_line
        self.headers = headers
        self.body = body
        
    def serialize_header(self):
        return self.status_line.serialize() + self.headers.serialize() + b'\r\n'
    
    def serialize(self):
        return self.serialize_header() + self.body

    @classmethod
    def from_raw_text(c, status_code, status_desc, body_raw = b''):
        return c(
            HTTPStatusLine('HTTP/1.1', status_code, status_desc),
            HTTPHeaders({
                'Content-Type': 'text/html; charset=utf-8',
                'Content-Length': str(len(body_raw))
            }),
            body_raw
        )

    @classmethod
    def from_text(c, status_code, status_desc, body_decoded = ''):
        return c.from_raw_text(status_code, status_desc, body_decoded.encode())

