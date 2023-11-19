import socket
import threading
import selectors

from ..log import log_print, LogLevel


class TCPSocketServer:
    backlog_size = 10
    select_interval = 0.2
    
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.sock = None
        
        self.shutdown_signal = False
        self.is_shutdown = threading.Event()
    
    def get_sockets_in_selector(self):
        return [key.fileobj for key in self.selector.get_map().values()]
    
    def launch(self):
        try:
            # create welcome socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.hostname, self.port))
            self.sock.listen(self.backlog_size)
            
            # register welcome socket
            self.selector.register(self.sock, selectors.EVENT_READ)
            
            # serve
            while not self.shutdown_signal:
                events = self.selector.select(self.select_interval)
                
                for key, mask in events:
                    connection: socket.socket = key.fileobj
                    
                    if connection == self.sock:
                        # welcome socket is triggered
                        self.launch_connection()
                    else:
                        # connection socket is triggered
                        try:
                            self.handle_connection(connection)
                        except ConnectionResetError:
                            self.shutdown_connection(connection)
        finally:
            self.shutdown_signal = False
            self.is_shutdown.set()
            self.sock.close()
    
    def shutdown(self):
        self.shutdown_signal = True
        self.is_shutdown.wait()
    
    def launch_connection(self):
        # accept and register connection socket
        connection, address = self.sock.accept()
        self.selector.register(connection, selectors.EVENT_READ)
        log_print(f'Connection from {address[0]}:{address[1]} registered', LogLevel.INFO)

    def shutdown_connection(self, connection):
        address = connection.getpeername()
        
        # unregister connection socket
            # TODO: 这么写的话, 在关闭服务器后其它 client recv(x) 会一直收到 b'', 不会有异常
        self.selector.unregister(connection)
        connection.shutdown(socket.SHUT_WR)
        connection.close()
        log_print(f'Connection from {address[0]}:{address[1]} unregistered', LogLevel.INFO)

    def handle_connection(self, connection):
        pass

