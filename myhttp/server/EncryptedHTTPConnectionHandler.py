from enum import Enum

from . import BaseConnectionHandlerClass
from ..log import log_print, LogLevel
from ..message import HTTPRequestLine, HTTPHeaders, HTTPRequestMessage
from ..content import HTTPResponseGenerator
from ..exception import HTTPStatusException


class RecvBufferTargetType(Enum):
    LENGTH = 0          # require for length -> [target_length]
    MARKER = 1          # require for marker -> [target_marker]
    NO_TARGET = 2       # received all (no target)


class RecvBufferState(Enum):
    HEADER = 0          # receiving header
    BODY = 1            # receiving body (content-length)
    CHUNK_SIZE = 2      # receiving chunk size (chunked)
    CHUNK_DATA = 3      # receiving chunk data (chunked)
    ALL = 4             # received all


class RecvBufferManager:
    def __init__(self):
        self.concatenate_buffer = b'' # may contain part of next request at the end of each request, so only be cleared in __init__()
        self.prepare()
    
    def set_target(self, target_type, target_value = None, next_state = None):
        self.target_type = target_type
        if target_type == RecvBufferTargetType.LENGTH:
            self.target_length = target_value
        elif target_type == RecvBufferTargetType.MARKER:
            self.target_marker = target_value
        else: # target_type == RecvTargetType.NO_TARGET
            next_state = RecvBufferState.ALL
        self.state = next_state

    def prepare(self):
        self.header = b''
        self.request_line_encapsulated = None
        self.headers_encapsulated = None
        self.body = b''
        self.set_target(RecvBufferTargetType.MARKER, b'\r\n\r\n', RecvBufferState.HEADER)


class EncryptedHTTPConnectionHandler(BaseConnectionHandlerClass):
    recv_buffer_size = 4096
    
    def __init__(self, connection, server):
        super().__init__(connection, server)
        self.recv_buffer_manager = RecvBufferManager()
        self.last_request = None # each connection will only handle one request at a time
        self.additional_data = {}
    
    def send_response(self, response, header_only = False): # header_only for HEAD, 和 GET 的头完全一致即可，不用改变 Content-Length 等
        if not header_only:
            self.send(response.serialize())
        else:
            self.send(response.serialize_header())
    
    def send_chunk(self, chunk_content):
        if not isinstance(chunk_content, bytes):
            chunk_content = chunk_content.encode()
        self.send(f'{len(chunk_content):X}\r\n'.encode() + chunk_content + b'\r\n')
    
    """
        Handle HTTP status errors from `connection`
    """
    def error_handler(self, code, desc, extend_headers = {}, request = None):
        self.last_request = request
        
        if not self.server.http_error_handler(code, desc, extend_headers, self):
            self.send_response(self.connection, HTTPResponseGenerator.by_content_type(
                body = f'{code} {desc}',
                content_type = 'text/plain',
                version = self.http_version if not request else request.request_line.version,
                status_code = code,
                status_desc = desc
            ))
    
    """
        Handle a single encapsulated request from `connection`
    """
    def request_handler(self, request):
        self.last_request = request
        
        # TODO: 加密 here
        log_print('EncryptedHTTPConnectionHandler.request_handler()', LogLevel.INFO)
        
        # add default Connection header
        if not request.headers.is_exist('Connection'):
            if self.http_version == 'HTTP/1.1':
                request.headers.set('Connection', 'keep-alive')
            elif self.http_version == 'HTTP/1.0':
                request.headers.set('Connection', 'close')
        
        # handle request
        try:
            self.server.http_route_handler(self)
        except HTTPStatusException as e:
            self.error_handler(e.status_code, e.status_desc, e.extend_headers, request)
        except Exception:
            self.error_handler(500, HTTPStatusException.default_status_description[500], e.extend_headers, request) # TODO: ensure the server will not crash due to one of the connections
        
        # close connection if Connection: close
        if request.headers.is_exist('Connection') and request.headers.get('Connection').lower() == 'close':
            self.shutdown()
    
    """ Override """
    def handle(self):
        # get recv buffer manager
        r = self.recv_buffer_manager
        
        # receive data
        peek_data = self.connection.recv(self.recv_buffer_size) # the connection may be closed by client ConnectionAbortedError will be handled outside
        if not peek_data:
            # TODO: what has happened?
            self.shutdown()
        else:
            log_print(f'Data from <{self.address[0]}:{self.address[1]}>: {peek_data}', 'RAW_DATA')
            r.concatenate_buffer += peek_data
            
            while True: # keep on trying to finish and publish targets
                target_finished = False
                target_acquired = None
                if r.target_type == RecvBufferTargetType.LENGTH:
                    if len(r.concatenate_buffer) >= r.target_length:
                        target_acquired = r.concatenate_buffer[:r.target_length]
                        r.concatenate_buffer = r.concatenate_buffer[r.target_length:]
                        target_finished = True
                elif r.target_type == RecvBufferTargetType.MARKER:
                    find_idx = r.concatenate_buffer.find(r.target_marker)
                    if find_idx >= 0:
                        target_acquired = r.concatenate_buffer[:find_idx]
                        r.concatenate_buffer = r.concatenate_buffer[(find_idx + len(r.target_marker)):]
                        target_finished = True
                else: # recv.target_type == RecvTargetType.NO_TARGET
                    target_finished = True
                
                if target_finished:
                    if r.state == RecvBufferState.HEADER:
                        r.header = target_acquired
                        try:
                            # parse request line
                            eorl = r.header.find(b'\r\n')
                            r.request_line_encapsulated = HTTPRequestLine.from_parsing(r.header[:eorl])
                            
                            # parse headers
                            r.headers_encapsulated = HTTPHeaders.from_parsing(r.header[(eorl + 2):])
                            if r.headers_encapsulated.is_exist('Content-Length'):
                                r.set_target(RecvBufferTargetType.LENGTH, int(r.headers_encapsulated.get('Content-Length')), RecvBufferState.BODY)
                            elif r.headers_encapsulated.is_exist('Transfer-Encoding'):
                                r.set_target(RecvBufferTargetType.MARKER, b'\r\n', RecvBufferState.CHUNK_SIZE)
                            else:
                                # TODO: no Content-Length or Transfer-Encoding, no body in default
                                r.set_target(RecvBufferTargetType.LENGTH, 0, RecvBufferState.BODY)
                        except HTTPStatusException as e:
                            self.error_handler(e.status_code, e.status_desc)
                            self.shutdown() # TODO: 如果是 handle_connection 过程中出错，这里直接选择关闭连接
                            break
                    elif r.state == RecvBufferState.BODY:
                        r.body = target_acquired
                        r.set_target(RecvBufferTargetType.NO_TARGET)
                    elif r.state == RecvBufferState.CHUNK_SIZE:
                        chunk_size = int(target_acquired, 16)
                        r.set_target(RecvBufferTargetType.LENGTH, chunk_size + 2, RecvBufferState.CHUNK_DATA) # to include \r\n
                    elif r.state == RecvBufferState.CHUNK_DATA:
                        chunk_data = target_acquired[:-2] # to exclude \r\n
                        if len(chunk_data) == 0:
                            r.set_target(RecvBufferTargetType.NO_TARGET)
                        else:
                            r.body += chunk_data
                            r.set_target(RecvBufferTargetType.MARKER, b'\r\n', RecvBufferState.CHUNK_SIZE)
                    else: # recv.state == RecvState.ALL:
                        self.request_handler(HTTPRequestMessage(r.request_line_encapsulated, r.headers_encapsulated, r.body))
                        r.prepare()
                else:
                    break # latest target not finished, break the loop and wait for next peek_data
    
    """ Override """
    def setup(self):
        log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: setup()', LogLevel.INFO)
    
    """ Override """
    def finish(self):
        log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: finish()', LogLevel.INFO)

