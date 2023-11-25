from enum import Enum

from . import TCPSocketServer
from ..log import log_print, LogLevel
from ..message import URLUtils, HTTPRequestLine, HTTPHeaders, HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine
from ..exception import HTTPStatusException
from ..content import HTTPResponseGenerator


"""
    RecvTargetType:
        0: require for length -> [target_length]
        1: require for marker -> [target_marker]
        2: received all (no target)
"""
class RecvTargetType(Enum):
    LENGTH = 0
    MARKER = 1
    NO_TARGET = 2


"""
    RecvState:
        0: receiving header
        1: receiving body (content-length)
        2: receiving chunk size (chunked)
        3: receiving chunk data (chunked)
        4: received all
"""
class RecvState(Enum):
    HEADER = 0
    BODY = 1
    CHUNK_SIZE = 2
    CHUNK_DATA = 3
    ALL = 4


"""
    Object for storing data and flags when receiving data during a specific connection
"""
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


"""
    Pool for storing RecvPoolObject for HTTP server
    register and fetch using connections as handles
"""
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


"""
    RouteTree:
        tree: RouteTreeNode
"""
class RouteTree:
    class Node:
        def __init__(self):
            self.funcs = {}
            self.children = {}
        
        def __str__(self):
            return f'funcs: {self.funcs}, children: {self.children}'
    
    def __init__(self):
        self.tree = RouteTree.Node()

    def extend(self, path_list, func, methods):
        # TODO: path is case-insensitive?
        node = self.tree
        for path in path_list:
            if not node.children.__contains__(path):
                node.children[path] = RouteTree.Node()
            node = node.children[path]
        if type(methods) == str:
            methods = [methods]
        for method in methods:
            node.funcs[method] = func

    def search(self, path_list, method):
        node = self.tree
        idx = 0
        for path in path_list:
            if not node.children.__contains__(path):
                break
            node = node.children[path]
            idx += 1
        if not node.funcs.__contains__(method):
            return (None, None)
        return (node.funcs[method], path_list[idx:])


"""
    HTTPServer
"""
class HTTPServer(TCPSocketServer):
    http_version = 'HTTP/1.1'
    supported_methods = ['GET', 'HEAD', 'POST']
    recv_buffer_size = 4096
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port)
        
        self.route_tree = RouteTree() # route mapping tree shared by all connections
        
        self.server_error_handler = {} # error handler shared by all connections
        
        self.recv_pool = RecvPool() # each connection should have its own recv object
    
    def send_response(self, connection, response):
        self.connection_send(connection, response.serialize())
    
    def send_chunk(self, connection, chunk_raw = b''):
        self.connection_send(connection, f'{len(chunk_raw):X}\r\n'.encode() + chunk_raw + b'\r\n')
    
    def http_status_error_handler(self, e, connection, request = None):
        code = e.status_code
        desc = e.status_desc
        not_sent = True
        if self.server_error_handler:
            if self.server_error_handler.__contains__(code):
                self.server_error_handler[code](desc, connection, request)
                not_sent = False
            elif self.server_error_handler.__contains__(0):
                self.server_error_handler[0](code, desc, connection, request)
                not_sent = False
        if not_sent:
            self.send_response(connection, HTTPResponseGenerator.text_plain(
                body = f'{code} {desc}',
                version = self.http_version if not request else request.request_line.version,
                status_code = code,
                status_desc = desc
            ))
    
    """
        Handle an encapsulated request from `connection`
    """
    def handle_request(self, connection, request):
        # add default Connection header
        if not request.headers.is_exist('Connection'):
            if self.http_version == 'HTTP/1.1':
                request.headers.set('Connection', 'keep-alive')
            elif self.http_version == 'HTTP/1.0':
                request.headers.set('Connection', 'close')
        
        # handle request
        try:
            if not request.request_line.method in self.supported_methods:
                raise HTTPStatusException(405)
            
            url = URLUtils.from_parsing(request.request_line.path)
            path_matches, get_params = url.path_list, url.params
            
            func, arg_list = self.route_tree.search(path_matches, request.request_line.method)
            if not func:
                raise HTTPStatusException(404) # TODO: 一定是 404 吗？
            
            args_grp = {}
            args_grp['path'] = arg_list
            args_grp['connection'] = connection
            args_grp['request'] = request
            args_grp['parameters'] = get_params
            
            func(**args_grp)
        except HTTPStatusException as e:
            self.http_status_error_handler(e, connection, request)
        
        # close connection if Connection: close
        if request.headers.is_exist('Connection') and request.headers.get('Connection').lower() == 'close':
            self.shutdown_connection(connection)
    
    """
        Handle a recv from `connection`
        TODO: chunked mode receiving not tested
    """
    def handle_connection(self, connection):
        # fetch recv object from pool for this connection
        if not self.recv_pool.get(connection):
            recv = self.recv_pool.add(connection)
        recv = self.recv_pool.get(connection)
        
        # receive data
        peek_data = connection.recv(self.recv_buffer_size) # the connection may be closed by client ConnectionAbortedError will be handled outside
        if not peek_data:
            # TODO: what has happened?
            self.shutdown_connection(connection)
        else:
            address = connection.getpeername()
            log_print(f'Data from <{address[0]}:{address[1]}>: {peek_data}', 'RAW_DATA')
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
                        try:
                            # parse request line
                            eorl = recv.header.find(b'\r\n')
                            recv.request_line_encapsulated = HTTPRequestLine.from_parsing(recv.header[:eorl])
                            
                            # parse headers
                            recv.headers_encapsulated = HTTPHeaders.from_parsing(recv.header[(eorl + 2):])
                            if recv.headers_encapsulated.is_exist('Content-Length'):
                                recv.set_target(RecvTargetType.LENGTH, int(recv.headers_encapsulated.get('Content-Length')), RecvState.BODY)
                            elif recv.headers_encapsulated.is_exist('Transfer-Encoding'):
                                recv.set_target(RecvTargetType.MARKER, b'\r\n', RecvState.CHUNK_SIZE)
                            else:
                                # TODO: no Content-Length or Transfer-Encoding, no body in default
                                recv.set_target(RecvTargetType.LENGTH, 0, RecvState.BODY)
                        except HTTPStatusException as e:
                            self.http_status_error_handler(e, connection)
                            self.shutdown_connection(connection) # TODO: 如果是 handle_connection 过程中出错，这里直接选择关闭连接
                            break
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
    
    """
        Decorator for registering handler for specific path and method
            path <- ['part', 'of', 'GET', 'path', 'without', 'matched', 'route']
            connection <- connection object
            request <- request object
            parameters <- dict of GET parameters
    """
    def route(self, path, methods = 'GET'): # decorator allowing user to register handler for specific path and method
        """
            func(path, connection, request, parameters)
        """
        def wrapper(func):
            self.route_tree.extend(URLUtils.from_parsing(path).path_list, func, methods)
            return func
        return wrapper

    """
        Decorator for registering handler for error codes
    """
    def errorhandler(self, code):
        def wrapper(func):
            self.server_error_handler[code] = func
            return func
        return wrapper

