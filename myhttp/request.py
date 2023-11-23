from .message import HTTPRequestMessage, HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from .exception import HTTPStatusException


class SimpleHTTPRequestHandler:
    http_version = 'HTTP/1.1'
    supported_methods = ['GET', 'HEAD', 'POST']
    
    def __init__(self):
        self.route_table = None # view of HTTPServer.route_table
    
    def handle(self, connection, request):
        if request.request_line.method in self.supported_methods:
            return self.method_handler(connection, request)
        else:
            raise HTTPStatusException(405)
    
    def method_handler(self, connection, request):
        for params in self.route_table:
            if not (request.request_line.method in params['method']):
                continue
            match = params['compiled_pattern'].match(request.request_line.path)
            if match:
                match_grp = {key: value for key, value in match.groupdict().items() if value is not None}
                args_grp = {}
                
                args_grp['connection'] = connection
                args_grp['request'] = request
                
                if params['params'] and match_grp.__contains__('parameters'):
                    parameters = match_grp.pop('parameters')
                    args_grp['parameters'] = dict(pair.split("=") for pair in parameters.split("&")) if parameters else {}
                
                args_grp.update(match_grp)
                
                handler = params['handler']
                return handler(**args_grp)
        raise HTTPStatusException(404) # TODO: 一定是 404 吗？

