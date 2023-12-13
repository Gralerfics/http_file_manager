import base64
import socket
from myhttp.message import HTTPRequestMessage, HTTPRequestLine, HTTPHeaders, HTTPResponseMessage
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import os
class HTTPSClientClass():
    def get_response(self):
        buf = b""
        while len(buf) < 4 or buf[-4:] != b'\r\n\r\n':
            buf += self.client_socket.recv(1)
        status_line, headers = buf.split(b'\r\n', 1)
        status_line = HTTPRequestLine.from_parsing(status_line)
        headers = HTTPHeaders.from_parsing(headers)
        buf = b""
        while len(buf) < int(headers.get('Content-Length')):
            buf += self.client_socket.recv(self.recv_block_size)
        response = HTTPResponseMessage(status_line, headers, buf)
        return response
    
    
    def rsa_encrypt(self, message):
        rsa_cipher = PKCS1_OAEP.new(RSA.import_key(self.rsa_public_key))
        return rsa_cipher.encrypt(message)
    
    def aes_decrypt(self, message):
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
        return unpad(aes_cipher.decrypt(message), AES.block_size)

    def __init__(self, host, port, username, password):
        self.recv_block_size = 4096
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.host, self.port))
        self.authorization = "Basic " + base64.b64encode((username + ':' + password).encode('utf-8')).decode('utf-8')
        request = HTTPRequestMessage(
            HTTPRequestLine('GET', '/', 'HTTP/1.1'),
            HTTPHeaders({
                "Connection": "keep-alive",
                "Authorization": self.authorization,
                "MyEncryption": "request",
            }),
        )
        self.client_socket.send(request.serialize())
        server_message = self.get_response()
        
        self.rsa_public_key = server_message.body
        self.aes_key = get_random_bytes(16)
        self.aes_iv = get_random_bytes(16)

        request = HTTPRequestMessage(
            HTTPRequestLine('GET', '/', 'HTTP/1.1'),
            HTTPHeaders({
                "Connection": "keep-alive",
                "Authorization": self.authorization,
                "MyEncryption": "AES-KEY",
            }),
            self.rsa_encrypt(self.aes_key + self.aes_iv)
        )
        self.client_socket.send(request.serialize())
        server_message = self.get_response()

    
    def download_file(self, file_path, store_path, chunked): 
        assert chunked == 0 or chunked == 1
        if chunked == 0:
            request = HTTPRequestMessage(
                HTTPRequestLine('GET', file_path, 'HTTP/1.1'),
                HTTPHeaders({
                    'Connection': 'keep-alive',
                    "Authorization": self.authorization,
                    "MyEncryption": "AES-Transfer",
                }),
            )
            self.client_socket.send(request.serialize())
            server_message = self.get_response()
            server_message.update_body(self.aes_decrypt(server_message.body))
            store_path = os.path.join(store_path, os.path.basename(file_path))
            with open(store_path, 'wb') as f:
                f.write(server_message.body)
        else:
            request = HTTPRequestMessage(
                HTTPRequestLine('GET', file_path + '?chunked=1', 'HTTP/1.1'),
                HTTPHeaders({
                    'Connection': 'keep-alive',
                    "Authorization": self.authorization,
                    "MyEncryption": "AES-Transfer",
                }),
            )
            self.client_socket.send(request.serialize())
            buf = b""
            while len(buf) < 4 or buf[-4:] != b'\r\n\r\n':
                buf += self.client_socket.recv(1)
            status_line, headers = buf.split(b'\r\n', 1)
            status_line = HTTPRequestLine.from_parsing(status_line)
            headers = HTTPHeaders.from_parsing(headers)
            store_path = os.path.join(store_path, os.path.basename(file_path))
            file = open(store_path, 'wb')
            buf = b""
            while True:
                rec_buf = b""
                while len(rec_buf) < 2 or rec_buf[-2:] != b'\r\n':
                    rec_buf += self.client_socket.recv(1)
                lenth = int(rec_buf[:-2], 16)
                rec_buf = b""
                for i in range(0, lenth // self.recv_block_size):
                    rec_buf += self.client_socket.recv(self.recv_block_size)
                rec_buf += self.client_socket.recv(lenth % self.recv_block_size)
                self.client_socket.recv(2)
                if (lenth == 0):
                    break
                else:
                    file.write(self.aes_decrypt(rec_buf))
            file.close()


test = HTTPSClientClass("localhost", 80, "client1", "123")
test.download_file("/client1/hello.txt", "C:/Users/mayst/Desktop/http_file_manager/stored", 0)
test.download_file("/client1/project.pptx", "C:/Users/mayst/Desktop/http_file_manager/stored", 0)
test.download_file("/client1/Project3.pdf", "C:/Users/mayst/Desktop/http_file_manager/stored", 0)