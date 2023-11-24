from .message import URLUtils, HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from .exception import HTTPStatusException


class SimpleHTTPRequestHandler:
    http_version = 'HTTP/1.1'
    supported_methods = ['GET', 'HEAD', 'POST']
    
    def __init__(self):
        self.route_tree = None # view of HTTPServer.route_tree
    
    def handle(self, connection, request):
        if request.request_line.method in self.supported_methods:
            self.method_handler(connection, request)
            # return self.method_handler(connection, request)
        else:
            raise HTTPStatusException(405)
    
    def method_handler(self, connection, request):
        url = URLUtils.from_parsing(request.request_line.path)
        path_matches, get_params = url.path_list, url.params
        
        func, arg_list = self.route_tree.search(path_matches, request.request_line.method)
        if not func:
            raise HTTPStatusException(404) # TODO: 一定是 404 吗？
        
        args_grp = {}
        args_grp['path'] = arg_list
        args_grp['connection'] = connection
        args_grp['request'] = request
        args_grp['parameters'] = get_params
        
        func(**args_grp)
        # return func(**args_grp)

