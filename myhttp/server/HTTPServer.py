import re
from enum import Enum

from . import TCPSocketServer
from ..log import log_print, LogLevel
from ..message import HTTPRequestLine, HTTPHeaders, HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine
from ..request import SimpleHTTPRequestHandler
from ..exception import HTTPStatusException


class RecvTargetType(Enum):
    """
        0: require for length -> [target_length]
        1: require for marker -> [target_marker]
        2: received all (no target)
    """
    LENGTH = 0
    MARKER = 1
    NO_TARGET = 2


class RecvState(Enum):
    """
        0: receiving header
        1: receiving body (content-length)
        2: receiving chunk size (chunked)
        3: receiving chunk data (chunked)
        4: received all
    """
    HEADER = 0
    BODY = 1
    CHUNK_SIZE = 2
    CHUNK_DATA = 3
    ALL = 4


class RecvPoolObject:
    def __init__(self):
        self.concatenate_buffer = b'' # may contain part of next request at the end of each request, so only be cleared in __init__()
        self.prepare()
    
    def set_target(self, target_type, target_value = None, next_state = None):
        self.target_type = target_type
        if target_type == RecvTargetType.LENGTH:
            self.target_length = target_value
        elif target_type == RecvTargetType.MARKER:
            self.target_marker = target_value
        else: # target_type == RecvTargetType.NO_TARGET
            next_state = RecvState.ALL
        self.state = next_state
    
    def prepare(self):
        self.header = b''
        self.request_line_encapsulated = None
        self.headers_encapsulated = None
        self.body = b''
        self.set_target(RecvTargetType.MARKER, b'\r\n\r\n', RecvState.HEADER)


class RecvPool:
    def __init__(self):
        self.pool = {}
    
    def get(self, connection):
        if self.pool.__contains__(connection):
            return self.pool[connection]
        else:
            return None
    
    def add(self, connection):
        self.pool[connection] = RecvPoolObject()
        return self.pool[connection]
    
    def remove(self, connection):
        self.pool.pop(connection)


class HTTPServer(TCPSocketServer):
    recv_buffer_size = 5
    
    def __init__(self, hostname, port, request_handler = SimpleHTTPRequestHandler()):
        super().__init__(hostname, port)
        
        self.route_table = list() # route mapping shared by all connections
        
        self.request_handler = request_handler # request_handler shared by all connections
        self.request_handler.route_table = self.route_table
        
        self.decorator_error_handler = None # error handler shared by all connections
        
        self.recv_pool = RecvPool() # each connection should have its own recv object
    
    # TODO: 重来
    def handle_request(self, connection, request):
        # TODO: 确定是 1.1 版本吗？是否要在这里加入标头默认值自动添加？还是在 request handler 里？
        
        try:
            response = self.request_handler.handle(connection, request)
            # if not response:
            #     raise HTTPStatusException(500) # TODO
        except HTTPStatusException as e:
            code = e.status_code
            desc = HTTPStatusException.status_description[code]
            if self.decorator_error_handler:
                if self.decorator_error_handler['pass_request']:
                    response = self.decorator_error_handler['handler'](request, code, desc)
                else:
                    response = self.decorator_error_handler['handler'](code, desc)
            else:
                response = HTTPResponseMessage.from_text(code, desc, f'{code} {desc}'.encode())
        
        if response:
            # TODO: 目前如果 response 为空就不发送，代表 handle 中自己进行了发送操作，例如使用 transfer-encoding: chunked 发送响应的情况
            connection.send(response.serialize())
        
        if request.headers.headers.__contains__('Connection') and request.headers.headers['Connection'] == 'close':
            self.shutdown_connection(connection)
    
    # TODO: chunked mode not tested
    def handle_connection(self, connection): # handle a recv from `connection`
        # fetch recv object from pool for this connection
        if not self.recv_pool.get(connection):
            recv = self.recv_pool.add(connection)
        recv = self.recv_pool.get(connection)
        
        # receive data
        peek_data = connection.recv(self.recv_buffer_size)
        if not peek_data:
            # TODO: what has happened?
            self.shutdown_connection(connection)
        else:
            # address = connection.getpeername()
            # log_print(f'Data from <{address[0]}:{address[1]}>: {peek_data}', 'RAW_DATA')
            recv.concatenate_buffer += peek_data
            
            while True: # keep on trying to finish and publish targets
                target_finished = False
                target_acquired = None
                if recv.target_type == RecvTargetType.LENGTH:
                    if len(recv.concatenate_buffer) >= recv.target_length:
                        target_acquired = recv.concatenate_buffer[:recv.target_length]
                        recv.concatenate_buffer = recv.concatenate_buffer[recv.target_length:]
                        target_finished = True
                elif recv.target_type == RecvTargetType.MARKER:
                    find_idx = recv.concatenate_buffer.find(recv.target_marker)
                    if find_idx >= 0:
                        target_acquired = recv.concatenate_buffer[:find_idx]
                        recv.concatenate_buffer = recv.concatenate_buffer[(find_idx + len(recv.target_marker)):]
                        target_finished = True
                else: # recv.target_type == RecvTargetType.NO_TARGET
                    target_finished = True
                
                if target_finished:
                    if recv.state == RecvState.HEADER:
                        recv.header = target_acquired
                        
                        # parse request line
                        eorl = recv.header.find(b'\r\n')
                        recv.request_line_encapsulated = HTTPRequestLine.from_parsing(recv.header[:eorl])
                        
                        # parse headers
                        recv.headers_encapsulated = HTTPHeaders.from_parsing(recv.header[(eorl + 2):])
                        if recv.headers_encapsulated.headers.__contains__('Content-Length'):
                            recv.set_target(RecvTargetType.LENGTH, int(recv.headers_encapsulated.headers['Content-Length']), RecvState.BODY)
                        elif recv.headers_encapsulated.headers.__contains__('Transfer-Encoding'):
                            recv.set_target(RecvTargetType.MARKER, b'\r\n', RecvState.CHUNK_SIZE)
                        else:
                            # TODO: no Content-Length or Transfer-Encoding, no body in default
                            recv.set_target(RecvTargetType.LENGTH, 0, RecvState.BODY)
                    elif recv.state == RecvState.BODY:
                        recv.body = target_acquired
                        recv.set_target(RecvTargetType.NO_TARGET)
                    elif recv.state == RecvState.CHUNK_SIZE:
                        chunk_size = int(target_acquired, 16)
                        recv.set_target(RecvTargetType.LENGTH, chunk_size + 2, RecvState.CHUNK_DATA) # to include \r\n
                    elif recv.state == RecvState.CHUNK_DATA:
                        chunk_data = target_acquired[:-2] # to exclude \r\n
                        if len(chunk_data) == 0:
                            recv.set_target(RecvTargetType.NO_TARGET)
                        else:
                            recv.body += chunk_data
                            recv.set_target(RecvTargetType.MARKER, b'\r\n', RecvState.CHUNK_SIZE)
                    else: # recv.state == RecvState.ALL:
                        self.handle_request(connection, HTTPRequestMessage(recv.request_line_encapsulated, recv.headers_encapsulated, recv.body))
                        recv.prepare()
                else:
                    break # latest target not finished, break the loop and wait for next peek_data
    
    def route(self, path, method = 'GET', pass_request = False, pass_connection = False, pass_uriparams = False, re_path = False): # decorator allowing user to register handler for specific path and method
        """
            reserved keywords in path:
                request, parameters
        """
        
        def convert_pattern(path):
            pattern = re.sub(r'\${(\w+):d}', r'(?P<\1>[^?#]+)', path)
            pattern = re.sub(r'\${(\w+)}', r'(?P<\1>[^/?#]+)', pattern)
            pattern += r'(?:\?(?P<parameters>[^#]+))?'
            return f'^{pattern}$'
        
        def wrapper(func):
            path_pattern = path if re_path else convert_pattern(path)
            self.route_table.append({
                'compiled_pattern': re.compile(path_pattern),
                'method': method,
                'handler': func,
                'pass_connection': pass_connection,
                'pass_request': pass_request,
                'pass_uriparams': pass_uriparams
            })
            return func

        return wrapper

    def error(self, pass_request = False):
        def wrapper(func):
            self.decorator_error_handler = {
                'handler': func,
                'pass_request': pass_request
            }
            return func
        
        return wrapper

