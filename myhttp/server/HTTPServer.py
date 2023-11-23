from enum import Enum

from . import TCPSocketServer
from ..log import log_print, LogLevel
from ..message import URL, HTTPRequestLine, HTTPHeaders, HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine
from ..request import SimpleHTTPRequestHandler
from ..exception import HTTPStatusException


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
    recv_buffer_size = 4096
    
    def __init__(self, hostname, port, request_handler = SimpleHTTPRequestHandler()):
        super().__init__(hostname, port)
        
        self.route_tree = RouteTree() # route mapping tree shared by all connections
        
        self.server_request_handler = request_handler # request_handler shared by all connections
        self.server_request_handler.route_tree = self.route_tree
        
        self.server_error_handler = None # error handler shared by all connections
        
        self.recv_pool = RecvPool() # each connection should have its own recv object
    
    def send_response(self, connection, response):
        self.connection_send(connection, response.serialize())
    
    def send_chunk(self, connection, chunk_raw = b''):
        self.connection_send(connection, f'{len(chunk_raw):X}\r\n'.encode() + chunk_raw + b'\r\n')
    
    """
        Handle an encapsulated request from `connection`
    """
    def handle_request(self, connection, request):
        # TODO: add default headers according to HTTP version?
        try:
            self.server_request_handler.handle(connection, request)
        except HTTPStatusException as e:
            code = e.status_code
            desc = HTTPStatusException.status_description[code]
            if self.server_error_handler:
                self.server_error_handler(code, desc, connection, request)
            else:
                self.send_response(connection, HTTPResponseMessage.from_text(code, desc, f'{code} {desc}'))
        
        if request.headers.headers.__contains__('Connection') and request.headers.headers['Connection'] == 'close':
            self.shutdown_connection(connection)
    
    """
        Handle a recv from `connection`
        TODO: chunked mode not tested
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
            self.route_tree.extend(URL.from_parsing(path).path_list, func, methods)
            return func
        return wrapper

    """
        Decorator for registering handler for error codes
    """
    def errorhandler(self, func):
        self.server_error_handler = func
        return func

