import socket
import threading
import selectors

from ..log import log_print, LogLevel


class BaseConnectionHandlerClass:
    def __init__(self, connection):
        self.connection = connection
        self.address = connection.getpeername()
    
    def setup(self):
        # log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: setup()', LogLevel.INFO)
        pass
    
    def handle(self):
        # log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: handle()', LogLevel.INFO)
        pass
    
    def shutdown(self):
        # log_print(f'Connection from <{self.address[0]}:{self.address[1]}>: shutdown()', LogLevel.INFO)
        pass


class TCPSocketServer:
    backlog_size = 10
    select_timeout = 0.1
    
    def __init__(self, hostname, port, ConnectionHandlerClass = BaseConnectionHandlerClass):
        self.hostname = hostname
        self.port = port
        self.ConnectionHandlerClass = ConnectionHandlerClass
        
        self.welcome_socket = None
        self.selector = selectors.DefaultSelector()                         # IO multiplexing for sockets
        self.connection_handlers_map = {}                                   # connection socket -> connection handler
        
        self.shutdown_signal = False
        self.is_shutdown = threading.Event()
    
    def get_sockets_in_selector(self):
        return [key.fileobj for key in self.selector.get_map().values()]
    
    def launch(self):
        try:
            # create welcome socket
            self.welcome_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.welcome_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.welcome_socket.bind((self.hostname, self.port))
            self.welcome_socket.listen(self.backlog_size)
            
            # register welcome socket
            self.selector.register(self.welcome_socket, selectors.EVENT_READ)
            
            # serve
            while not self.shutdown_signal:
                events = self.selector.select(self.select_timeout) # timeout for shutdown_signal detection
                
                for key, mask in events:
                    connection: socket.socket = key.fileobj
                    
                    # TODO: 需要确认除了来新数据、连接 reset，还有什么情况会触发 welcome socket / connection socket 的变动吗？
                    if connection == self.welcome_socket:
                        # welcome socket is triggered
                        new_connection_handler = self.launch_connection()
                        self.connection_handlers_map[connection] = new_connection_handler
                    else:
                        # connection socket is triggered
                        try:
                            self.handle_connection(connection)
                        except ConnectionError: # containing ConnectionResetError, ConnectionAbortedError, etc.
                            self.shutdown_connection(connection)
        finally:
            self.shutdown_signal = False
            self.is_shutdown.set()
            self.welcome_socket.close()
    
    def shutdown(self):
        self.shutdown_signal = True
        self.is_shutdown.wait()
    
    def launch_connection(self):
        connection, address = self.welcome_socket.accept()                  # accept new connection socket
        self.selector.register(connection, selectors.EVENT_READ)            # register
        connection_handler = self.ConnectionHandlerClass(connection)        # encapsulate
        connection_handler.setup()                                          # lifecycle: setup()
        return connection_handler

    def handle_connection(self, connection):
        connection_handler = self.connection_handlers_map.get(connection)   # get connection handler
        connection_handler.handle()                                         # lifecycle: handle()

    def shutdown_connection(self, connection):
        connection_handler = self.connection_handlers_map.pop(connection)   # get and pop connection handler
        connection_handler.shutdown()                                       # lifecycle: shutdown()
        self.selector.unregister(connection)                                # unregister
        connection.shutdown(socket.SHUT_WR)
        connection.close()
        # TODO: 备注，这么写的话, 在关闭服务器后其它 client recv(x) 会一直收到 b'', 不会有异常
    
    # def connection_send(self, connection, data):
    #     log_print(f'Data to <{connection.getpeername()[0]}:{connection.getpeername()[1]}>: {data}', 'RAW_DATA')
    #     connection.send(data)

