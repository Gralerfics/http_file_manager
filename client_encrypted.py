import os
import base64
import socket

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

from myhttp.content import KeyUtils
from myhttp.message import HTTPRequestMessage, HTTPRequestLine, HTTPHeaders, HTTPResponseMessage


class EncryptedHTTPClient():
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
    
    def aes_encrypt(self, message):
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
        return aes_cipher.encrypt(pad(message, AES.block_size))
    
    def download(self, file_path, store_path, chunked): 
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
            with open(store_path, 'wb') as f:
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
                        f.write(self.aes_decrypt(rec_buf))

    def upload(self, target_path, source_path): 
        file_name = os.path.basename(source_path)
        boundry = KeyUtils.random_key()
        with open(source_path, "rb") as f:
            file_content = f.read()
        submit_body = f"--{boundry}\r\nContent-Disposition: form-data; name=\"{self.username}\"; filename=\"{file_name}\"\r\nContent-Type: text/plain\r\n\r\n".encode() + file_content + f"\r\n--{boundry}\r\n".encode()
        submit_body = self.aes_encrypt(submit_body)
        request = HTTPRequestMessage(
            HTTPRequestLine('POST', "/upload?path=" + target_path, 'HTTP/1.1'),
                HTTPHeaders({
                "Host": "localhost",
                "Content-Type": "multipart/form-data; boundary=" + boundry,
                "Connection": "keep-alive",
                "Authorization": self.authorization,
                "MyEncryption": "AES-Transfer",
            }),
            submit_body
        )
        self.client_socket.send(request.serialize())


def main():
    client = EncryptedHTTPClient("localhost", 80, "client1", "123")

    print(" =============== download =============== ")
    client.download("/client1/test/hello.txt", "./stored", 1)
    client.download("/client1/test/project.pptx", "./stored", 0)
    client.download("/client1/test/Project3.pdf", "./stored", 1)

    print(" =============== upload =============== ")
    client.upload("client1/test", "./stored/hello.txt")
    client.upload("client1/test", "./stored/project.pptx")
    client.upload("client1/test", "./stored/Project3.pdf")


if __name__ == "__main__":
    main()

