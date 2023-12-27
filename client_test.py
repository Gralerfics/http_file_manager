import socket

from myhttp.content import KeyUtils
from myhttp.message import HTTPRequestMessage, HTTPRequestLine, HTTPHeaders, HTTPResponseMessage

if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', 80))
    request = HTTPRequestMessage(
        HTTPRequestLine('GET', '/client1/hello.txt', 'HTTP/1.1'),
        HTTPHeaders({
            "Connection": "keep-alive",
            "Authorization": "Basic Y2xpZW50MToxMjM=",
            "MyEncryption": "request",
        }),
    )
    
    client_socket.send(request.serialize())
    recv = client_socket.recv(409600)
    print(recv[0:100])
    
    client_socket.send(request.serialize())
    recv = client_socket.recv(409600)
    print(recv[0:100])
    
    client_socket.close()

