from enum import Enum

from . import BaseConnectionHandlerClass
from ..log import log_print, LogLevel
from ..message import HTTPRequestLine, HTTPStatusLine, HTTPHeaders, HTTPRequestMessage, HTTPResponseMessage
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


# TODO: 想重构：之前因为一个 connection 同时只处理一个 request，所以把 request 作为 connection 的属性；
#       那么因为一个 request 应该只对应一个 response，所以可以把 response 也作为 connection 的属性？
#       如此在 route 或 error 的 handler 中的 send_response 即可只缓存待发送的 response，留到 request_handler 最后再实际发送。
#       这样的话可以把一些需要添加的 extend_headers 统一设置，不用到处混乱地进行参数传递。
#           例如 resource_handler 中的 parameter 就可以只用于传递需要渲染的参数，不用存重定向来的 extend_headers。
#           例如是上传下载操作中所有的 authentificate 之后都需要在响应中添加 Set-Cookie，可以统一存到 connection 中，不用每次发错误码之类还得加上。
#           粗略感觉应该是可以去掉全局所有的 extend_headers 参数？
#       以及这样的话发送 response 的 API 也更加合理。
#       顺便这样的话需要再斟酌一下 TEchunked 的情况。
#       确认：其他地方有改动吗？
#       为什么直接让 route 或 error handler 返回 response？
#           可以多次动态修改欲返回的 response；
#           再比如在 route A 中需要添加一个 header，然后后续需要跳转到 route B 的处理，可以去掉递归回溯的处理：
#               即如果 return response，需要 A 将 B 的 response 合并进来再返回，除去跳转还需要语句进行合并返回；
#               如果是公用于 connection 的 response，那么重定向时接力传入 connection_handler 即可。
#       EncryptedHTTPConnectionHandler 暂时先删除
class HTTPConnectionHandler(BaseConnectionHandlerClass):
    recv_buffer_size = 4096
    
    def __init__(self, connection, server):
        super().__init__(connection, server)
        
        self.request = None # each connection will only handle one request at a time
        self.recv_buffer_manager = RecvBufferManager()
        
        self.response = None
        self.refresh_response()
        self.chunked_launched = False # TODO: not allow to deactivate after activating and not allow to add Content-Length after activating.
        self.chunked_finished = False
        
        self.additional_data = {}
    
    """
        Response Management
    """
    
    def refresh_response(self):
        self.response = HTTPResponseMessage(
            HTTPStatusLine(self.server.http_version, 200, 'OK'),
            HTTPHeaders({'Content-Length': '0'}),
            b''
        )
    
    def launch_chunked_transfer(self):
        self.chunked_launched = True
        self.response.headers.remove('Content-Length')
        self.response.headers.set('Transfer-Encoding', 'chunked')
        self.send(self.response.serialize_header())
    
    def chunked_transmit(self, chunk_content):
        if self.chunked_launched:
            if self.request.request_line.method != 'HEAD':
                if not isinstance(chunk_content, bytes):
                    chunk_content = chunk_content.encode()
                self.send(f'{len(chunk_content):X}\r\n'.encode() + chunk_content + b'\r\n')
            # else: TODO: waste
        else:
            raise HTTPStatusException(500, 'Chunked Transfer Not Launched') # TODO
    
    def finish_chunked_transfer(self):
        if self.chunked_launched:
            self.chunked_finished = True
            if self.request.request_line.method != 'HEAD':
                self.send(b'0\r\n\r\n')
            # else: TODO: waste
        else:
            raise HTTPStatusException(500, 'Chunked Transfer Not Launched') # TODO
    
    """
        Handle HTTP status errors from `connection`
    """
    def error_handler(self, code, desc = None):
        if not desc:
            desc = HTTPStatusException.default_status_description[code]
        if self.request:
            self.response.update_version(self.request.request_line.version)
        if not self.server.http_error_handler(code, desc, self):
            self.response.update_status(code, desc)
            self.response.update_by_content_type(
                body = f'{code} {desc}',
                content_type = 'text/plain',
            )
    
    """
        Handle a single encapsulated request from `connection`
    """
    def request_handler(self):
        # add default Connection header
        if not self.request.headers.is_exist('Connection'):
            if self.server.http_version == 'HTTP/1.1':
                self.request.headers.set('Connection', 'keep-alive')
            elif self.server.http_version == 'HTTP/1.0':
                self.request.headers.set('Connection', 'close')
        
        # handle request
        self.response.update_version(self.request.request_line.version)
        try:
            self.server.http_route_handler(self)
        except HTTPStatusException as e:
            self.error_handler(e.status_code, e.status_desc)
        except Exception:
            # raise
            self.error_handler(500) # TODO: ensure the server will not crash due to one of the connections
        
        # send prepared response
        if not self.chunked_launched:
            self.send(self.response.serialize() if self.request.request_line.method != 'HEAD' else self.response.serialize_header())
        else:
            if not self.chunked_finished:
                raise(500, 'Chunked Transfer Not Terminated')
        
        # close connection if Connection: close
        if self.request.headers.is_exist('Connection') and self.request.headers.get('Connection').lower() == 'close':
            self.shutdown()
        
        # refresh response and request
        self.request = None
        self.refresh_response()
    
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
                        self.request = HTTPRequestMessage(r.request_line_encapsulated, r.headers_encapsulated, r.body)
                        self.request_handler()
                        r.prepare()
                else:
                    break # latest target not finished, break the loop and wait for next peek_data
    
    """ Override """
    def setup(self):
        log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: setup()', LogLevel.INFO)
    
    """ Override """
    def finish(self):
        log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: finish()', LogLevel.INFO)

