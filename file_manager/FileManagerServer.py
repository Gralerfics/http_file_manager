import threading
import mimetypes
import pickle
import shutil
import json
import time
import os

from myhttp.server import HTTPServer, HTTPConnectionHandler
from myhttp.exception import HTTPStatusException
from myhttp.content import HTTPBodyUtils, HTTPHeaderUtils, HTMLUtils, KeyUtils, HTTPResponseGenerator

from .page_renderer import *


class UserManager:
    # user data format: {'<username>': info}, info = {'password': password, 'email': email, ...}
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()

    def _read(self):
        if not os.path.exists(self.filepath):
            self._write({})
        
        self.lock.acquire()
        try:
            with open(self.filepath, 'rb') as file:
                data = pickle.load(file)
                return data if data else {}
        finally:
            self.lock.release()

    def _write(self, data):
        self.lock.acquire()
        try:
            with open(self.filepath, 'wb') as file:
                pickle.dump(data, file)
        finally:
            self.lock.release()

    def register(self, username, password, update_info = {}):
        data = self._read()
        data[username] = {'password': password, **update_info}
        self._write(data)
    
    def get(self, username):
        data = self._read()
        return data.get(username, None)

    def remove(self, username):
        data = self._read()
        if username in data:
            del data[username]
            self._write(data)

    def authenticate(self, username, password):
        data = self._read()
        return data.get(username, {}).get('password') == password


class CookieManager:
    # cookie data format: {'<cookie>': info}, info = {'username': username, 'time_stamp': time_stamp, ...}
    default_expire_time = 1000 * 1000 * 1000 * 60 * 60 * 24 * 7
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()

    def _read(self):
        if not os.path.exists(self.filepath):
            self._write({})
        
        self.lock.acquire()
        try:
            with open(self.filepath, 'rb') as file:
                data = pickle.load(file)
                return data if data else {}
        finally:
            self.lock.release()

    def _write(self, data):
        self.lock.acquire()
        try:
            with open(self.filepath, 'wb') as file:
                pickle.dump(data, file)
        finally:
            self.lock.release()

    def get(self, cookie):
        data = self._read()
        return data.get(cookie, None)

    def new(self, username, time_stamp, expire_time = default_expire_time, extend_info = {}):
        data = self._read()
        cookie = KeyUtils.random_key(not_in = data)
        data[cookie] = {'username': username, 'time_stamp': time_stamp, 'expire_time': expire_time, **extend_info}
        self._write(data)
        return cookie
    
    # TODO: timely remove expired cookies

    def remove(self, cookie):
        data = self._read()
        if cookie in data:
            del data[cookie]
            self._write(data)


"""
    FileManagerServer
        all the `path` (`<user>/<path>`) in this class is relative to `root_dir`
"""
class FileManagerServer(HTTPServer):
    """
        Routes
    """
    
    def resource_handler(path, parameters, connection_handler): # parameters: dict -> variables to be rendered
        request = connection_handler.last_request
        server: FileManagerServer = connection_handler.server
        
        virtual_path = '/'.join(path)                                                       # target path (virtual)
        
        if not server.is_exist(virtual_path, resourse = True):                              # path not exist
            raise HTTPStatusException(404)

        if not server.is_file(virtual_path, resourse = True):                               # path is not a file
            raise HTTPStatusException(400)
        
        response = get_resources_rendered(virtual_path, parameters.get('variables', {}), connection_handler, parameters.get('extend_headers', {}))
        connection_handler.send_response(response, header_only = (request.request_line.method == 'HEAD'))
    
    def api_user_register(path, parameters, connection_handler):
        request = connection_handler.last_request
        server = connection_handler.server
        
        if len(path) > 2:
            raise HTTPStatusException(400)
        
        # TODO: 后端 API 接口, POST, 注册用户
            # 注意用户不能叫 upload, delete, frontend_res, backend_api, etc.
        pass

    def fetch_handler(path, parameters, connection_handler):
        request = connection_handler.last_request
        server: FileManagerServer = connection_handler.server
        
        if not request.request_line.method == 'GET':                                        # method should be GET
            raise HTTPStatusException(405)
        
        virtual_path = '/'.join(path)                                                       # target path (virtual)
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate, TODO: 理解为虽然访问其它用户目录不需要验证，但无论如何必须处于登录状态
        extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
        
        if not server.is_exist(virtual_path):                                               # path not exist
            raise HTTPStatusException(404, extend_headers = extend_headers)
        
        if server.is_directory(virtual_path): # and path[-1] == '':                         # 如果确实是目录，则忽略缺少末尾斜杠的错误
            # TODO: 把对目录的 GET 请求视作对目录下的 view_directory_template.html 的资源请求，重定向到资源渲染器
                # 就是请求网页会慢一些，可能因为渲染过程
            FileManagerServer.resource_handler(['view_directory_template.html'], {
                'variables': {
                    'virtual_path': virtual_path,
                    'scan_list': server.list_directory(virtual_path),
                },
                'extend_headers': extend_headers
            }, connection_handler)
        elif server.is_file(virtual_path): # path[-1] != '':
            if parameters.get('chunked', '0') == '0':
                # direct download
                connection_handler.send_response(HTTPResponseGenerator.by_file_path(
                    file_path = server.root_dir + virtual_path,
                    version = request.request_line.version,
                    extend_headers = extend_headers
                ), header_only = (request.request_line.method == 'HEAD'))
            else:
                # chunked download
                file_type, file_encoding = mimetypes.guess_type(server.root_dir + virtual_path)
                content_disposition = 'inline'
                if not file_type:
                    file_type = 'application/octet-stream'
                    content_disposition = 'attachment'
                
                extend_headers['Content-Disposition'] = f'{content_disposition}; filename="{path[-1]}"'
                extend_headers['Transfer-Encoding'] = 'chunked'
                connection_handler.send_response(HTTPResponseGenerator.by_content_type(
                    content_type = file_type,
                    version = request.request_line.version,
                    extend_headers = extend_headers
                ), header_only = True)
                if request.request_line.method != 'HEAD':
                    with open(server.root_dir + virtual_path, 'rb') as f:
                        while True:
                            chunk_content = f.read(4096)
                            if not chunk_content:
                                connection_handler.send_chunk(b'')
                                break
                            connection_handler.send_chunk(chunk_content)
        else:
            raise HTTPStatusException(404, extend_headers = extend_headers)
    
    def upload_handler(path, parameters, connection_handler):
        request = connection_handler.last_request
        server: FileManagerServer = connection_handler.server
        
        if not request.request_line.method == 'POST':                                       # method should be POST
            raise HTTPStatusException(405)
        
        if len(path) > 1 or not parameters.__contains__('path'):                            # TODO: 400 Bad Request?
            raise HTTPStatusException(400)
        
        virtual_path = parameters['path'].strip('/')                                        # target path (virtual)
        located_user = server.belongs_to(virtual_path)                                      # target user
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate
        extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
        if username != located_user:                                                        # wrong user
            raise HTTPStatusException(403, extend_headers = extend_headers)
        
        if not server.is_exist(virtual_path):                                               # path not exist, TODO: setup directory?
            server.mkdir(virtual_path)
            # raise HTTPStatusException(404, extend_headers = extend_headers)
        
        if not server.is_directory(virtual_path):                                           # TODO: 必须为目录吧。
            raise HTTPStatusException(403, extend_headers = extend_headers)
        
        server.upload_file(virtual_path, request)
        
        connection_handler.send_response(HTTPResponseGenerator.by_content_type(
            version = request.request_line.version,
            extend_headers = extend_headers
        ))

    def delete_handler(path, parameters, connection_handler):
        request = connection_handler.last_request
        server: FileManagerServer = connection_handler.server
        
        if not request.request_line.method == 'POST':                                       # method should be POST
            raise HTTPStatusException(405)
        
        if len(path) > 1 or not parameters.__contains__('path'):                            # TODO: 400 Bad Request?
            raise HTTPStatusException(400)
        
        virtual_path = parameters['path'].strip('/')                                        # target path (virtual)
        located_user = server.belongs_to(virtual_path)                                      # target user
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate
        extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
        if username != located_user:                                                        # wrong user
            raise HTTPStatusException(403, extend_headers = extend_headers)
        
        if not server.is_exist(virtual_path):                                               # path not exist
            raise HTTPStatusException(404, extend_headers = extend_headers)
        
        server.delete_file(virtual_path)                                                    # delele file or directory from disk
        
        connection_handler.send_response(HTTPResponseGenerator.by_content_type(
            version = request.request_line.version,
            extend_headers = extend_headers
        ))
    
    """
        Initialization
    """
        
    def join_absoluted_path(dir):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
    
    def regularize_route(route):
        return '/' + route.strip('/')
    
    def __init__(
        self, hostname, port, ConnectionHandlerClass = HTTPConnectionHandler,
        root_dir = join_absoluted_path('data/'),
        reg_dir = join_absoluted_path('reg/'),
        res_route = '/file_manager_frontend_res',
        api_route = '/file_manager_backend_api',
        fetch_route = '/file_manager_fetch',
        upload_route = '/file_manager_upload',
        delete_route = '/file_manager_delete'
    ):
        super().__init__(hostname, port, ConnectionHandlerClass)
        
        self.res_route = FileManagerServer.regularize_route(res_route)
        self.api_route = FileManagerServer.regularize_route(api_route)
        self.fetch_route = FileManagerServer.regularize_route(fetch_route)
        self.upload_route = FileManagerServer.regularize_route(upload_route)
        self.delete_route = FileManagerServer.regularize_route(delete_route)
        
        self.route(self.res_route, methods = 'GET')(FileManagerServer.resource_handler)
        self.route(self.api_route + '/user_register', methods = 'POST')(FileManagerServer.api_user_register)
        self.route(self.fetch_route, methods = ['GET', 'HEAD', 'POST'])(FileManagerServer.fetch_handler)
        self.route(self.upload_route, methods = ['GET', 'HEAD', 'POST'])(FileManagerServer.upload_handler)
        self.route(self.delete_route, methods = ['GET', 'HEAD', 'POST'])(FileManagerServer.delete_handler)
        
        self.root_dir = root_dir
        self.reg_dir = reg_dir
        self.res_dir = FileManagerServer.join_absoluted_path('res/') # absolute path
        
        self.user_manager = UserManager(self.reg_dir + 'users.pkl')
        self.cookie_manager = CookieManager(self.reg_dir + 'cookies.pkl')
    
    """
        Information
    """
    
    def get_path(self, virtual_path, resourse = False):
        prefix = self.res_dir if resourse else self.root_dir
        return prefix + virtual_path
    
    def is_exist(self, virtual_path, resourse = False):
        prefix = self.res_dir if resourse else self.root_dir
        real_path = prefix + virtual_path
        return os.path.exists(real_path)
    
    def is_directory(self, virtual_path, resourse = False):
        prefix = self.res_dir if resourse else self.root_dir
        real_path = prefix + virtual_path
        return os.path.isdir(real_path)
    
    def is_file(self, virtual_path, resourse = False):
        prefix = self.res_dir if resourse else self.root_dir
        real_path = prefix + virtual_path
        return os.path.isfile(real_path)

    def belongs_to(self, virtual_path):
        if virtual_path == '':
            return None
        split = virtual_path.split('/')
        return split[0] if self.is_exist(split[0]) and self.is_directory(split[0]) else None
    
    def list_directory(self, path):
        real_path = self.root_dir + path.strip('/') + '/'
        with os.scandir(real_path) as it:
            dir_list = [entry.name + ('/' if os.path.isdir(real_path + entry.name) else '') for entry in it]
            return json.dumps(dir_list)
    
    """
        Verification
    """
    
    def authenticate(self, connection_handler):
        request = connection_handler.last_request
        authenicated = False
        new_cookie = None
        # there is a cookie: check if it is valid
        if not authenicated and request.headers.is_exist('Cookie'):
            cookie_dict = HTTPHeaderUtils.parse_cookie(request.headers.get('Cookie')) # parse cookie
            session_id = cookie_dict.get('session-id', None)
            if session_id:
                cookie_info = self.cookie_manager.get(session_id) # fetch cookie
                if cookie_info: # cookie exists
                    username, time_stamp, expire_time = cookie_info.get('username'), cookie_info.get('time_stamp'), cookie_info.get('expire_time')
                    if time_stamp + expire_time < time.time_ns(): # timeout detection
                        self.cookie_manager.remove(session_id)
                    else:
                        authenicated = True
                        # TODO: 通过 cookie 访问需要更新 cookie 的 time_stamp 吗？
        # no cookie or cookie is invalid: check if there is valid authorization
        if not authenicated and request.headers.is_exist('Authorization'):
            username, password = HTTPHeaderUtils.parse_authorization_basic(request.headers.get('Authorization')) # parse authorization
            if username and password:
                if self.user_manager.authenticate(username, password):
                    new_cookie = self.cookie_manager.new(username, time.time_ns(), 10 * 1000 * 1000 * 1000)
                    authenicated = True
        # neither is valid
        if not authenicated:
            raise HTTPStatusException(401, extend_headers = {'WWW-Authenticate': 'Basic realm="Authorization Required"'})
        # return username and new cookie
        return (username, new_cookie)
            # if not authenicated, raise 401, no need to return
            # if authenicated, return (username, new_cookie); new_cookie is not None when authenicated by Authorization, otherwise None

    """
        Manipulations
    """
    
    def mkdir(self, virtual_path):
        real_path = self.root_dir + virtual_path
        try:
            os.makedirs(real_path)
        except Exception:
            raise HTTPStatusException(500) # TODO: unexpected os error
    
    def upload_file(self, virtual_path, request):
        real_path = self.root_dir + virtual_path.strip('/') + '/' # guarantee that the path is end with '/'
        
        parsed = False
        file_errer = False
        if request.headers.is_exist('Content-Type'):
            content_type_dict = HTTPHeaderUtils.parse_content_type(request.headers.get('Content-Type'))
            mimetype_list = [key for key, value in content_type_dict.items() if value is None]
            if not mimetype_list or len(mimetype_list) != 1:
                raise HTTPStatusException(400)
            mimetype = mimetype_list[0]
            if mimetype == 'multipart/form-data':
                boundary = content_type_dict.get('boundary', None)
                if boundary:
                    file_list = HTTPBodyUtils.parse_multipart_form_data(request.body, boundary)
                    if file_list is not None:
                        parsed = True
                        for file in file_list:
                            filename = file.get('filename', None)
                            content = file.get('content', None)
                            # 重名覆盖
                            if filename is not None and content is not None:
                                try:
                                    with open(real_path + filename, 'wb') as f:
                                        f.write(content)
                                except Exception: # TODO: unexpected os error
                                    file_errer = True
            else:
                pass # TODO: 其它 MIME 类型呢？至少加上请求体直接为文件内容的基本类型。
        if file_errer:
            raise HTTPStatusException(500)
        if not parsed:
            raise HTTPStatusException(400) # TODO: Content-Type is required
    
    def delete_file(self, virtual_path): # TODO: 用户自己根根目录的处理
        real_path = self.root_dir + virtual_path
        if os.path.isfile(real_path):
            os.remove(real_path)
        else:
            shutil.rmtree(real_path)
            # os.removedirs(real_path)
    
    """
        Page Rendering
    """
    
    def error_page(self, code, desc):
        return get_error_page_rendered(code, desc, server = self)

