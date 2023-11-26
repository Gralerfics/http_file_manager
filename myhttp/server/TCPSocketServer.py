import socket
import threading
import selectors

from ..log import log_print


class BaseConnectionHandlerClass:
    def __init__(self, connection, server):
        self.connection = connection
        self.address = connection.getpeername()
        self.server = server
    
    """ Override """
    def setup(self):
        # to be overridden
        pass
    
    """ Override """
    def handle(self):
        # to be overridden
        pass
    
    """ Override """
    def finish(self):
        # to be overridden
        pass
    
    def send(self, data):
        log_print(f'Data to <{self.address[0]}:{self.address[1]}>: {data}', 'RAW_DATA')
        self.connection.send(data)
    
    def shutdown(self):
        self.finish()                                                       # lifecycle: finish()
        self.server.selector.unregister(self.connection)                    # unregister
        self.connection.shutdown(socket.SHUT_WR)
        self.connection.close()
        # TODO: 备注，这么写的话, 在关闭服务器后其它 client recv(x) 会一直收到 b'', 不会有异常


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
                        self.connection_handlers_map[new_connection_handler.connection] = new_connection_handler
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
        connection_handler = self.ConnectionHandlerClass(connection, self)  # encapsulate
        connection_handler.setup()                                          # lifecycle: setup()
        return connection_handler

    def handle_connection(self, connection):
        connection_handler = self.connection_handlers_map.get(connection)   # get connection handler
        connection_handler.handle()                                         # lifecycle: handle()

    def shutdown_connection(self, connection):
        connection_handler = self.connection_handlers_map.pop(connection)   # get and pop connection handler
        connection_handler.shutdown()                                       # shutdown connection handler

