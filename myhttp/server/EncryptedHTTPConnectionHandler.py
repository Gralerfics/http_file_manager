from enum import Enum

from . import BaseConnectionHandlerClass
from ..log import log_print, LogLevel
from ..message import HTTPRequestLine, HTTPStatusLine, HTTPHeaders, HTTPRequestMessage, HTTPResponseMessage
from ..exception import HTTPStatusException

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


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


class EncryptionKeyManager:
    def __init__(self):
        rsa_key = RSA.generate(2048)
        self.rsa_private_key = rsa_key.export_key()
        self.rsa_public_key = rsa_key.publickey().export_key()
        self.aes_key = None
    
    def rsa_encrypt(self, data):
        cipher_rsa = PKCS1_OAEP.new(RSA.import_key(self.rsa_public_key))
        return cipher_rsa.encrypt(data)
    
    def rsa_decrypt(self, data):
        cipher_rsa = PKCS1_OAEP.new(RSA.import_key(self.rsa_private_key))
        return cipher_rsa.decrypt(data)

    def set_aes_key(self, aes_key, iv):
        assert self.aes_key == None
        self.aes_key = aes_key
        self.iv = iv
    
    def aes_encrypt(self, data):
        self.aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv=self.iv)
        ciphertext = self.aes_cipher.encrypt(pad(data, AES.block_size))
        return ciphertext
    
    def aes_decrypt(self, data):
        self.aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv=self.iv)
        decrypted_message = unpad(self.aes_cipher.decrypt(data), AES.block_size)
        return decrypted_message
    
    def get_rsa_public_key(self):
        return self.rsa_public_key


class EncryptedHTTPConnectionHandler(BaseConnectionHandlerClass):
    recv_buffer_size = 4096
    
    def __init__(self, connection, server):
        super().__init__(connection, server)
        
        self.request = None # each connection will only handle one request at a time
        self.recv_buffer_manager = RecvBufferManager()
        
        self.response = None
        self.refresh_response()
        
        self.my_encryption_ready = False
        
        self.additional_data = {}
    
    """
        Response Management
    """
    
    def refresh_response(self):
        self.reset_chunked_transfer()
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
                if self.request.headers.get('MyEncryption').lower() == 'aes-transfer':
                    self.response.headers.set('MyEncryption', 'aes-transfer')
                    chunk_content = self.encrypted_helper.aes_encrypt(chunk_content)
                    self.send(f'{len(chunk_content):X}\r\n'.encode() + chunk_content + b'\r\n')
                else:
                    raise HTTPStatusException(400, 'Chunked Transfer Without Encryption Not Supported')
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
    
    def reset_chunked_transfer(self):
        self.chunked_launched = False
        self.chunked_finished = False
    
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
        
        # shaking and decryption
        encrypt_op = self.request.headers.get('MyEncryption')
        if encrypt_op is not None:
            encrypt_op = encrypt_op.lower()
        else:
            encrypt_op = 'none'
        
        if encrypt_op == 'request':
            # client asks for rsa public key -> generate and send rsa public key
            self.encrypted_helper = EncryptionKeyManager()
            rsa_public_key = self.encrypted_helper.get_rsa_public_key()
            
            self.response.headers.set('MyEncryption', 'rsa_public_key_response')
            self.response.update_by_content_type(rsa_public_key, 'text/plain')
        elif encrypt_op == 'aes-key':
            # client sends aes key (encrypted by rsa public key) -> decrypt and set aes key
            aes_key_iv = self.encrypted_helper.rsa_decrypt(self.request.body)
            aes_key = aes_key_iv[:16]
            aes_iv = aes_key_iv[16:]
            self.encrypted_helper.set_aes_key(aes_key, aes_iv)
            self.my_encryption_ready = True
            
            self.response.headers.set('MyEncryption', 'aes_set_complete')
            self.response.update_body(b'')
        elif encrypt_op == 'aes-transfer':
            if self.my_encryption_ready:
                # client sends encrypted data -> decrypt using aes key
                if self.request.headers.is_exist("Content-Length") and int(self.request.headers.get("Content-Length")) > 0: # TODO: ValueError
                    self.request.body = self.encrypted_helper.aes_decrypt(self.request.body)
                    self.request.headers.set("Content-Length", str(len(self.request.body)))
                
                # handle request
                self.response.update_version(self.request.request_line.version)
                try:
                    self.server.http_route_handler(self)
                except HTTPStatusException as e:
                    self.error_handler(e.status_code, e.status_desc)
                except Exception:
                    # raise
                    self.error_handler(500) # TODO: ensure the server will not crash due to one of the connections
            else:
                self.error_handler(400, 'Encryption Not Ready')
        elif encrypt_op == 'none':
            self.error_handler(400, 'Encryption Must Be Used')
        else:
            self.error_handler(400, 'Encryption Operation Not Supported')
        
        # send prepared response
        if not self.chunked_launched:
            if encrypt_op == 'aes-transfer': # e.g. when 'request', the response should not be encrypted
                # self.response.headers.set('content-type', 'text/plain')
                self.response.headers.set('MyEncryption', 'aes-transfer')
                self.response.update_body(self.encrypted_helper.aes_encrypt(self.response.body))
            self.send(self.response.serialize() if self.request.request_line.method != 'HEAD' else self.response.serialize_header())
        else:
            if not self.chunked_finished:
                self.error_handler(500, 'Chunked Transfer Not Terminated')
        
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

