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
rsa_public_key = server_message.body
print("RSA Public Key:", rsa_public_key)

aes_key = get_random_bytes(16)
aes_iv = get_random_bytes(16)
print("AES Key:", aes_key)
print("AES IV:", aes_iv)

rsa_cipher = PKCS1_OAEP.new(RSA.import_key(rsa_public_key))
encrypted_message = rsa_cipher.encrypt(aes_key + aes_iv)
print("Encrypted Message:", encrypted_message)

request = HTTPRequestMessage(
    HTTPRequestLine('GET', '/', 'HTTP/1.1'),
    HTTPHeaders({
        "Connection": "keep-alive",
        "Authorization": "Basic Y2xpZW50MToxMjM=",
        "MyEncryption": "AES-KEY",
    }),
    encrypted_message
)

client_socket.send(request.serialize())

server_message = HTTPResponseMessage.from_parsing(client_socket.recv(1024))
print("Server Message:", server_message.serialize())

aes_cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
aes_decipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_iv)
encrypted_message = aes_cipher .encrypt(pad(b"Hello World!", AES.block_size))
request = HTTPRequestMessage(
    HTTPRequestLine('GET', '/', 'HTTP/1.1'),
    HTTPHeaders({
        "Connection": "keep-alive",
        "Authorization": "Basic Y2xpZW50MToxMjM=",
        "MyEncryption": "test",
    }),
    encrypted_message
)
client_socket.send(request.serialize())
server_message = HTTPResponseMessage.from_parsing(client_socket.recv(1024))
print("Server Message:", server_message.serialize())

decipher_text = unpad(aes_decipher.decrypt(server_message.body), AES.block_size)
print(decipher_text)