from .exception import HTTPMessageError


class HTTPRequestLine:
    def __init__(self, method, path, version):
        self.method = method
        self.path = path
        self.version = version
    
    def serialize(self):
        return f'{self.method} {self.path} {self.version}\r\n'.encode()
    
    @staticmethod
    def parse(line):
        # e.g. b'GET / HTTP/1.1'
        splitted = line.decode().split(' ')
        return HTTPRequestLine(splitted[0], splitted[1], splitted[2])


class HTTPStatusLine:
    def __init__(self, version, status_code, status_desc):
        self.version = version
        self.status_code = status_code
        self.status_desc = status_desc
    
    def serialize(self):
        return f'{self.version} {self.status_code} {self.status_desc}\r\n'.encode()
    
    @staticmethod
    def parse(line):
        # e.g. b'HTTP/1.1 200 OK'
        splitted = line.decode('utf-8').split(' ')
        try:
            stat_code = int(splitted[1])
        except ValueError:
            raise HTTPMessageError('Invalid status code')
        return HTTPStatusLine(splitted[0], stat_code, splitted[2])


class HTTPHeaders:
    def __init__(self, headers = {}):
        self.headers = headers
    
    def serialize(self):
        return ''.join([f'{key}: {value}\r\n' for key, value in self.headers.items()]).encode()

    @staticmethod
    def parse(lines):
        headers = {}
        splitted = lines.split(b'\r\n')
        for line in splitted:
            splitted = line.decode('utf-8').split(': ')
            if len(splitted) == 2:
                headers[splitted[0]] = splitted[1]
            elif len(line) != 0:
                raise HTTPMessageError('Invalid header')
        return HTTPHeaders(headers)


class HTTPRequestMessage:
    def __init__(self, request_line, headers, body = b'\r\n'):
        # TODO: (下同) 空请求体是默认 b'\r\n' 吗？
        self.request_line = request_line
        self.headers = headers
        self.body = body
    
    def serialize(self):
        return self.request_line.serialize() + self.headers.serialize() + b'\r\n' + self.body


class HTTPResponseMessage:
    def __init__(self, status_line, headers, body = b'\r\n'):
        self.status_line = status_line
        self.headers = headers
        self.body = body
    
    def serialize(self):
        return self.status_line.serialize() + self.headers.serialize() + b'\r\n' + self.body

