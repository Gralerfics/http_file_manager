from . import TCPSocketServer, HTTPConnectionHandler
from ..message import HTTPURLUtils
from ..exception import HTTPStatusException


"""
    RouteTree:
        tree: RouteTreeNode
"""
class RouteTree:
    class Node:
        def __init__(self):
            self.funcs = {}
            self.children = {}
        
        def __str__(self):
            return f'funcs: {self.funcs}, children: {self.children}'
    
    def __init__(self):
        self.tree = RouteTree.Node()

    def extend(self, path_list, func, methods):
        # TODO: path is case-insensitive?
        node = self.tree
        for path in path_list:
            if not node.children.__contains__(path):
                node.children[path] = RouteTree.Node()
            node = node.children[path]
        if type(methods) == str:
            methods = [methods]
        for method in methods:
            node.funcs[method] = func

    def search(self, path_list, method):
        node = self.tree
        idx = 0
        for path in path_list:
            if not node.children.__contains__(path):
                break
            node = node.children[path]
            idx += 1
        if not node.funcs.__contains__(method):
            return (None, None)
        return (node.funcs[method], path_list[idx:])


class HTTPServer(TCPSocketServer):
    http_version = 'HTTP/1.1'
    supported_methods = ['GET', 'HEAD', 'POST']
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port, HTTPConnectionHandler)
        self.http_route_tree = RouteTree()
        self.http_error_handlers = {}
    
    """
        HTTP Error Handler
            code <- int
            desc <- str
            connection_handler <- HTTPConnectionHandler
    """
    def http_error_handler(self, code, desc, extend_headers, connection_handler):
        if self.http_error_handlers:
            if self.http_error_handlers.__contains__(code):
                self.http_error_handlers[code](desc, extend_headers, connection_handler)
                return True
            elif self.http_error_handlers.__contains__(0):
                self.http_error_handlers[0](code, desc, extend_headers, connection_handler)
                return True
        return False
    
    """
        HTTP Route Handler
            connection_handler <- HTTPConnectionHandler
    """
    def http_route_handler(self, connection_handler):
        request = connection_handler.last_request
        
        if not request.request_line.method in self.supported_methods:
            raise HTTPStatusException(405)
        
        url = HTTPURLUtils.from_parsing(request.request_line.path)
        path_matches, get_params = url.path_list, url.params
        
        func, arg_list = self.http_route_tree.search(path_matches, request.request_line.method)
        if not func:
            raise HTTPStatusException(404) # TODO: 一定是 404 吗？
        
        args_grp = {}
        args_grp['path'] = arg_list
        args_grp['parameters'] = get_params
        args_grp['connection_handler'] = connection_handler
        
        func(**args_grp)
    
    """
        Decorator for registering handler for specific path and method
            path <- ['part', 'of', 'GET', 'path', 'without', 'matched', 'route']
            parameters <- dict of GET parameters
            connection_handler <- connection handler object
    """
    def route(self, path, methods = 'GET'):
        """
            func(path, parameters, connection_handler)
        """
        def wrapper(func):
            self.http_route_tree.extend(HTTPURLUtils.from_parsing(path).path_list, func, methods)
            return func
        return wrapper

    """
        Decorator for registering handler for error codes
    """
    def errorhandler(self, code):
        def wrapper(func):
            self.http_error_handlers[code] = func
            return func
        return wrapper

