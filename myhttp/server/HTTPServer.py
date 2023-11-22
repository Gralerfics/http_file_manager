from . import TCPSocketServer
from ..log import log_print, LogLevel
from ..message import HTTPRequestLine, HTTPHeaders, HTTPRequestMessage


class HTTPServer(TCPSocketServer):
    recv_buffer_size = 4096
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port)
        
        self.recv_concatenate_buffer = b'' # may contain part of next request at the end of each request, so only be cleared in __init__()
        self.recv_prepare_for_next_request()
    
    def recv_set_target(self, target_type, target_value = None, next_state = None):
        self.recv_target_type = target_type
        if target_type == 0:
            self.recv_target_length = target_value
        elif target_type == 1:
            self.recv_target_marker = target_value
        else: # target_type == 2
            next_state = 4
        self.recv_state = next_state
    
    def recv_prepare_for_next_request(self):
        self.recv_header = b''
        self.recv_request_line_encapsulated = None
        self.recv_headers_encapsulated = None
        self.recv_body = b''
        
        self.recv_set_target(target_type = 1, target_value = b'\r\n\r\n', next_state = 0)
        # [recv_target_type]
            # 0: require for length -> [recv_target_length]
            # 1: require for marker -> [recv_target_marker]
            # 2: received all (no target)
        # [recv_state]
            # 0: receiving header
            # 1: receiving body (content-length)
            # 2: receiving chunk size (chunked)
            # 3: receiving chunk data (chunked)
            # 4: received all
    
    def handle_request(self, http_request):
        # TODO: 确定是 1.1 版本吗？是否要在这里加入标头默认值自动添加？还是在 request handler 里？
        # TODO: 调用 request handler 处理（给出 request，返回 response），代其返回 response，可能做些处理
        # TODO: 关于 Connection: Close 的处理
        
        print(http_request.request_line.method)
        print(http_request.request_line.path)
        print(http_request.request_line.version)
        print(http_request.headers.headers)
        print(http_request.body)
        
        pass
    
    def handle_connection(self, connection):
        peek_data = connection.recv(self.recv_buffer_size)
        if not peek_data:
            # TODO: what has happened?
            self.shutdown_connection(connection)
        else:
            address = connection.getpeername()
            log_print(f'Data from <{address[0]}:{address[1]}>: {peek_data}', 'RAW_DATA')
            self.recv_concatenate_buffer += peek_data
            
            while True: # keep on trying to finish and publish targets
                target_finished = False
                target_acquired = None
                if self.recv_target_type == 0:
                    # require for length
                    if len(self.recv_concatenate_buffer) >= self.recv_target_length:
                        target_acquired = self.recv_concatenate_buffer[:self.recv_target_length]
                        self.recv_concatenate_buffer = self.recv_concatenate_buffer[self.recv_target_length:]
                        target_finished = True
                elif self.recv_target_type == 1:
                    # require for marker
                    find_idx = self.recv_concatenate_buffer.find(self.recv_target_marker)
                    if find_idx >= 0:
                        target_acquired = self.recv_concatenate_buffer[:find_idx]
                        self.recv_concatenate_buffer = self.recv_concatenate_buffer[(find_idx + len(self.recv_target_marker)):]
                        target_finished = True
                else: # self.recv_target_type == 2
                    # received all
                    target_finished = True
                
                if target_finished:
                    if self.recv_state == 0:
                        # header finished
                        self.recv_header = target_acquired
                        
                        # parse request line
                        eorl = self.recv_header.find(b'\r\n')
                        self.recv_request_line_encapsulated = HTTPRequestLine.parse(self.recv_header[:eorl])
                        
                        # parse headers
                        self.recv_headers_encapsulated = HTTPHeaders.parse(self.recv_header[(eorl + 2):])
                        if self.recv_headers_encapsulated.headers.__contains__('Content-Length'):
                            self.recv_set_target(
                                target_type = 0,
                                target_value = int(self.recv_headers_encapsulated.headers['Content-Length']),
                                next_state = 1
                            ) # to receive body by content-length
                        elif self.recv_headers_encapsulated.headers.__contains__('Transfer-Encoding'):
                            self.recv_set_target(
                                target_type = 1,
                                target_value = b'\r\n',
                                next_state = 2
                            ) # to receive chunk size
                        else: # TODO: 都没有默认 body 为空？
                            self.recv_set_target(
                                target_type = 0,
                                target_value = 0,
                                next_state = 1
                            ) # to receive empty body
                    elif self.recv_state == 1:
                        # body by content-length finished
                        self.recv_body = target_acquired
                        self.recv_set_target(
                            target_type = 2
                        ) # to finish
                    elif self.recv_state == 2:
                        # chunk size by chunked finished
                        chunk_size = int(target_acquired, 16)
                        self.recv_set_target(
                            target_type = 0,
                            target_value = chunk_size + 2, # to include \r\n
                            next_state = 3
                        ) # to receive chunk data
                    elif self.recv_state == 3:
                        # chunk data by chunked finished
                        chunk_data = target_acquired[:-2] # to exclude \r\n
                        if len(chunk_data) == 0:
                            self.recv_set_target(
                                target_type = 2
                            ) # to finish
                        else:
                            self.recv_body += chunk_data
                            self.recv_set_target(
                                target_type = 1,
                                target_value = b'\r\n',
                                next_state = 2
                            ) # to receive next chunk size
                    else: # self.recv_state == 4:
                        # received all
                        self.handle_request(HTTPRequestMessage(self.recv_request_line_encapsulated, self.recv_headers_encapsulated, self.recv_body))
                        self.recv_prepare_for_next_request()
                else:
                    break # latest target not finished, break the loop and wait for next peek_data

