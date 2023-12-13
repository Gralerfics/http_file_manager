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

request = HTTPRequestMessage(
    HTTPRequestLine('GET', '/client1/hello.txt', 'HTTP/1.1'),
    HTTPHeaders({
        'Connection': 'keep-alive',
        "Authorization": "Basic Y2xpZW50MToxMjM=",
        "MyEncryption": "AES-Transfer",
    }),
)

client_socket.send(request.serialize())
server_message = HTTPResponseMessage.from_parsing(client_socket.recv(1024))
print('服务端消息：', server_message.serialize())

if server_message.headers.get('myencryption').lower() != 'aes-transfer':
    
    print('服务端消息：', server_message.serialize())
else:
    aes_decipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_iv)
    decipher_text = unpad(aes_decipher.decrypt(server_message.body), AES.block_size)
    server_message.body = decipher_text
    print('服务端消息：', server_message.serialize())



request = HTTPRequestMessage(
    HTTPRequestLine('GET', '/client1/hello.txt?chunked=1', 'HTTP/1.1'),
    HTTPHeaders({
        'Connection': 'keep-alive',
        "Authorization": "Basic Y2xpZW50MToxMjM=",
        "MyEncryption": "AES-Transfer",
    }),
)


client_socket.send(request.serialize())
server_message = client_socket.recv(1024)
while True:
    rec_buf = client_socket.recv(1024)
    splited = rec_buf.split(b'\r\n')
    lenth, cipher_text = int(splited[0]), splited[1]
    if lenth > 0:
    # print("![DEBUG] ", lenth, cipher_text)
        aes_decipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_iv)
        decipher_text = unpad(aes_decipher.decrypt(cipher_text), AES.block_size)
        lenth = len(decipher_text)
    else:
        decipher_text = b''
    print("![DEBUG] ", lenth, decipher_text)
    server_message += rec_buf
    if server_message[-5:] == b'0\r\n\r\n':
        break

print("server_message:", server_message)
# server_message = HTTPResponseMessage.from_parsing(buf)
# print('服务端消息：', server_message.serialize())
