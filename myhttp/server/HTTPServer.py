from ..log import log_print, LogLevel
from . import TCPSocketServer


class HTTPServer(TCPSocketServer):
    # self.
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port)
    
    def handle_connection(self, connection):
        # test handler
        data = connection.recv(1024)
        if not data:
            self.shutdown_connection(connection)
        else:
            log_print(f'{data}', 'HANDLE_CONNECTION')


# handle_connection 是 connection socket 变动后的处理函数：
#       希望：
#           在这里 recv 报文原文，包括超出缓冲区后多次读取并拼接，保证得到的是完整的一次报文
#           得到的报文原文利用 myhttp.message 中的工具进行解析，得到 HTTPRequest 对象
#           针对不同的方法（GET、POSE、HEAD），调用不同的处理函数
#               这部分处理应该是各次报文独立的（？）
#           还有不同的 header：
#               这部分处理可能涉及整个 connection 的状态
#                   例如 cookie、connection
#                   这不是指 stateful
#       需要确认：除了来新数据、连接 reset，还有什么情况会触发 connection socket 的变动？

