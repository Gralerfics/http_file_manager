import socket

from myhttp.message import HTTPRequestMessage, HTTPRequestLine, HTTPHeaders, HTTPResponseMessage
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from myhttp.server import HTTPServerEncryptedClass

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

host = 'localhost'
port = 80

client_socket.connect((host, port))

# request = HTTPRequestMessage(
#     HTTPRequestLine('GET', '/client1/hello.txt', 'HTTP/1.1'),
#     HTTPHeaders({
#         'Connection': 'keep-alive',
#         "Authorization": "Basic Y2xpZW50MToxMjM="
#     }),
#     b'hello'
# )
# client_socket.send(request.serialize())

# server_message = client_socket.recv(1024).decode('utf-8')
# print('服务端消息：', server_message)

request = HTTPRequestMessage(
    HTTPRequestLine('GET', '/', 'HTTP/1.1'),
    HTTPHeaders({
        "Connection": "keep-alive",
        "Authorization": "Basic Y2xpZW50MToxMjM=",
        "MyEncryption": "request",
    }),
    b''
)

client_socket.send(request.serialize())

server_message = HTTPResponseMessage.from_parsing(client_socket.recv(1024))

# server_message = HTTPHeaders.from_parsing(server_message)
print('服务端消息：', server_message.serialize())


