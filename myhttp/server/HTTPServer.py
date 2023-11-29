from . import TCPSocketServer, HTTPConnectionHandler
from ..message import HTTPUrl
from ..exception import HTTPStatusException


"""
    RouteTree
        函数绑定时 .../name/ 和 .../name 效果一致;
        函数匹配时 .../name/ 和 .../name 会匹配到相同函数，前者传回 path = ['']，后者会传回 path = [].
"""
class RouteTree:
    class Node:
        def __init__(self):
            self.priority = {} # method -> priority; only when there is a func, there is a priority (>=0)
            self.funcs = {} # method -> func
            self.children = {}
        
        def __str__(self):
            return f'funcs: {self.funcs}, children: {self.children}'
    
    def __init__(self):
        self.tree = RouteTree.Node()

    def extend(self, path_list, func, methods: list[str], priority: list[int]):
        # path is case-sensitive
        node = self.tree
        for path in path_list:
            if not path: # if path == '', do not go deeper
                break
            if not node.children.__contains__(path):
                node.children[path] = RouteTree.Node()
            node = node.children[path]
        # if type(methods) == str:
        #     methods = [methods]
        # if type(priority) == int:
        #     priority = [priority]
        for method, prior in zip(methods, priority):
            if prior > node.priority.get(method, -1): # if priority is higher (>) than the previous one or there is no previous one, replace it
                node.priority[method] = prior
                node.funcs[method] = func

    def search(self, path_list, method):
        node = self.tree
        idx = 0
        for path in path_list:
            if not path: # if path == '', do not go deeper
                break
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
    
    def __init__(self, hostname, port, ConnectionHandlerClass = HTTPConnectionHandler):
        super().__init__(hostname, port, ConnectionHandlerClass)
        self.http_route_tree = RouteTree()
        self.http_error_handlers = {}
    
    """
        HTTP Error Handler
            code <- int
            desc <- str
            connection_handler <- HTTPConnectionHandler
    """
    def http_error_handler(self, code, desc, connection_handler):
        if self.http_error_handlers:
            if self.http_error_handlers.__contains__(code):
                self.http_error_handlers[code](desc, connection_handler)
                return True
            elif self.http_error_handlers.__contains__(0):
                self.http_error_handlers[0](code, desc, connection_handler)
                return True
        return False
    
    """
        HTTP Route Handler
            connection_handler <- HTTPConnectionHandler
    """
    def http_route_handler(self, connection_handler):
        request = connection_handler.request
        
        if not request.request_line.method in self.supported_methods:
            raise HTTPStatusException(405)
        
        url = HTTPUrl.from_parsing(request.request_line.path)
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
        
        Also you can manually register handler like this:
            server.route(path, methods)(func)
    """
    def route(self, path, methods = ['GET'], priority = None): # TODO: priority not tested
        """
            methods = ['A', 'B', 'C'] -> priority = [x, y, z]
        """
        if type(methods) == str:
            methods = [methods]
        if not priority:
            priority = [0] * len(methods)
        
        assert len(methods) == len(priority)
        
        def wrapper(func):
            self.http_route_tree.extend(HTTPUrl.from_parsing(path).path_list, func, methods, priority)
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

