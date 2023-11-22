from .message import HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from .exception import HTTPStatusException


class SimpleHTTPRequestHandler:
    http_version = 'HTTP/1.1'
    
    def __init__(self):
        self.route_table = None # view of HTTPServer.route_table
    
    def handle(self, request: HTTPRequestMessage):
        method_handler = 'method_handler_' + request.request_line.method
        if hasattr(self, method_handler):
            return getattr(self, method_handler)(request)
        else:
            raise HTTPStatusException(405)
    
    # TODO: 统一几个 method_handler
    def method_handler_GET(self, request):
        # TODO: 模式匹配 path
        key = (request.request_line.path, request.request_line.method)
        if self.route_table and self.route_table.__contains__(key):
            handler = self.route_table[key]
            handler(request)
            raise HTTPStatusException(200) # TODO: 改 response
        else:
            raise HTTPStatusException(404) # TODO: 细分

    def method_handler_HEAD(self, request):
        pass
    
    def method_handler_POST(self, request):
        pass

