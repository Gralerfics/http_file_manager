import threading
import mimetypes
import pickle
import shutil
import json
import time
import os

from myhttp.server import HTTPServer, HTTPConnectionHandler
from myhttp.exception import HTTPStatusException
from myhttp.content import HTTPBodyUtils, HTTPHeaderUtils, HTMLUtils, KeyUtils

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
    
    # 注意尽量不要在各种报错之前加有些 response 的部分
        # 例如后面报错了，但前面添加的部分功能性 header 没有被错误页的 header 覆盖掉，有小概率会混乱
        # 为什么不在错误处理中冲刷 response？因为 cookie 等仍然需要保留，header 类型太多不方便考虑所有情况
        # 有必要的话调用者可以在 errorhandler route 中自行冲刷
    def resource_handler(path, parameters, connection_handler): # parameters -> variables to be rendered
        request = connection_handler.request
        server = connection_handler.server
        response = connection_handler.response
        
        virtual_path = '/'.join(path)                                                       # target path (virtual)
        
        if not server.is_exist(virtual_path, resourse = True):                              # path not exist
            raise HTTPStatusException(404)

        if not server.is_file(virtual_path, resourse = True):                               # path is not a file
            raise HTTPStatusException(400, 'Resource Not File')
        
        response.update_by_file_path(server.get_path(virtual_path, resourse = True))
        response.update_body(HTMLUtils.render_template(response.body.decode(), {
            **parameters,
            **get_file_manager_rendering_extended_variables(server)
        }).encode())
    
    def api_user_register(path, parameters, connection_handler):
        request = connection_handler.request
        server = connection_handler.server
        
        if len(path) > 0:
            raise HTTPStatusException(404)
        
        # TODO: 后端 API 接口, POST, 注册用户
            # 注意用户不能叫 upload, delete, frontend_res, backend_api, etc.
        pass

    def fetch_handler(path, parameters, connection_handler):
        request = connection_handler.request
        server = connection_handler.server
        response = connection_handler.response
        
        if not request.request_line.method == 'GET':                                        # method should be GET
            raise HTTPStatusException(405)
        
        virtual_path = '/'.join(path)                                                       # target path (virtual)
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate, TODO: 理解为虽然访问其它用户目录不需要验证，但无论如何必须处于登录状态
        if new_cookie:
            response.update_header('Set-Cookie', f'session-id={new_cookie}')
        
        if not server.is_exist(virtual_path):                                               # path not exist, wrong path like `/abc/def.jpg/` (when `def.jpg` is in fact a file) will failed in this step
            raise HTTPStatusException(404)
        
        if server.is_directory(virtual_path): # and path[-1] == '':                         # 如果确实是目录，则忽略缺少末尾斜杠的错误
            if parameters.get('SUSTech-HTTP', '0') != '0':
                # SUSTech-HTTP == 1, return json list
                response.update_by_content_type(
                    body = server.list_directory(virtual_path),
                    content_type = 'application/json',
                )
            else:
                # SUSTech-HTTP != 1, return html page
                FileManagerServer.resource_handler(['view_directory_template.html'], {      # 把对目录的 GET 请求视作对目录下的 view_directory_template.html 的资源请求，重定向到资源渲染器
                    'virtual_path': virtual_path,
                    'scan_list': server.list_directory(virtual_path),
                }, connection_handler)
        elif server.is_file(virtual_path): # path[-1] != '':
            # file type
            file_type, file_encoding = mimetypes.guess_type(server.root_dir + virtual_path)
            content_disposition = 'inline'
            if not file_type:
                file_type = 'application/octet-stream'
                content_disposition = 'attachment'
            response.update_header('Accept-Ranges', 'bytes') # TODO
            
            # download type
            if parameters.get('chunked', '0') == '1':
                # chunked download, TODO: 不用 update_by_file_path 为了效率，或许可以给这些函数加个 header_only？
                response.update_header('Content-Type', file_type)
                response.update_header('Content-Disposition', f'{content_disposition}; filename="{path[-1]}"')
                
                connection_handler.launch_chunked_transfer()
                # if request.request_line.method != 'HEAD':
                # TODO: threading transmitting?
                with open(server.get_path(virtual_path), 'rb') as f:
                    while True:
                        chunk_content = f.read(4096)
                        if not chunk_content:
                            connection_handler.finish_chunked_transfer()
                            break
                        connection_handler.chunked_transmit(chunk_content)
            elif request.headers.is_exist('Range'): # TODO: 目录页面需要支持 Range 吗？需要的话还得放到外面
                # range download
                with open(server.get_path(virtual_path), 'rb') as f: # TODO: 不全部读入，按照 Range 需求移动文件指针
                    file = f.read()
                    file_length = len(file)
                
                ranges, unit = HTTPHeaderUtils.parse_range(request.headers.get('Range'), content_length = file_length)
                if unit != 'bytes':
                    raise HTTPStatusException(416) # TODO: only support bytes now
                if ranges:
                    response.update_status(206)
                    if len(ranges) == 1:
                        response.update_header('Content-Type', file_type)
                        response.update_header('Content-Range', f'bytes {ranges[0][0]}-{ranges[0][1]}/{file_length}')
                        response.update_body(file[ranges[0][0] : (ranges[0][1] + 1)])
                    else:
                        boundary = KeyUtils.random_key()
                        response.update_header('Content-Type', f'multipart/byteranges; boundary={boundary}')
                        body = f'--{boundary}'.encode()
                        for r in ranges:
                            body += f'\r\nContent-Type: {file_type}\r\n'.encode()
                            body += f'Content-Range: bytes {r[0]}-{r[1]}/{file_length}\r\n\r\n'.encode()
                            body += file[r[0] : (r[1] + 1)]
                            body += f'\r\n--{boundary}'.encode()
                        body += b'--\r\n'
                        response.update_body(body)
            else:
                # direct download
                response.update_by_file_path(server.get_path(virtual_path))
        else:
            raise HTTPStatusException(404)
    
    def upload_handler(path, parameters, connection_handler):
        request = connection_handler.request
        server = connection_handler.server
        response = connection_handler.response
        
        if not request.request_line.method == 'POST':                                       # method should be POST
            raise HTTPStatusException(405)
        
        if not parameters.__contains__('path'):                                             # param path not exist
            raise HTTPStatusException(400, 'Param Path Not Exist')
        
        virtual_path = parameters.get('path').strip('/')                                    # target path (virtual)
        located_user = server.belongs_to(virtual_path)                                      # target user
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate
        if new_cookie:
            response.update_header('Set-Cookie', f'session-id={new_cookie}')
        if username != located_user:                                                        # wrong user
            raise HTTPStatusException(403)
        
        if not server.is_exist(virtual_path):                                               # path not exist
            # 路径不存在时，如果是用户根目录，创建用户目录，否则报 404
            if virtual_path == username:
                server.mkdir(virtual_path)
            else:
                raise HTTPStatusException(404)
        
        if not server.is_directory(virtual_path):                                           # must be a directory, TODO: which code
            raise HTTPStatusException(400, 'Target Path Not Directory')
        
        server.upload_file(virtual_path, request)                                           # save uploaded file to disk
        # response is 200 OK in default

    def delete_handler(path, parameters, connection_handler):
        request = connection_handler.request
        server = connection_handler.server
        response = connection_handler.response
        
        if not request.request_line.method == 'POST':                                       # method should be POST
            raise HTTPStatusException(405)
        
        if not parameters.__contains__('path'):                                             # param path not exist
            raise HTTPStatusException(400, 'Param Path Not Exist')
        
        virtual_path = parameters.get('path').strip('/')                                        # target path (virtual)
        located_user = server.belongs_to(virtual_path)                                      # target user
        
        username, new_cookie = server.authenticate(connection_handler)                      # authenticate
        if new_cookie:
            response.update_header('Set-Cookie', f'session-id={new_cookie}')
        if username != located_user:                                                        # wrong user
            raise HTTPStatusException(403)
        
        if not server.is_exist(virtual_path):                                               # path not exist
            raise HTTPStatusException(404)
        
        server.delete_file(virtual_path)                                                    # delele file or directory from disk
        # response is 200 OK in default
    
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
        virtual_path = virtual_path.strip('/')
        if virtual_path == '':
            return None
        split = virtual_path.split('/')
        return split[0]
        # return split[0] if self.is_exist(split[0]) and self.is_directory(split[0]) else None
            # TODO: 现在只管返回第一个就是了，不判断这是否是个用户目录
    
    def list_directory(self, path):
        real_path = self.root_dir + path.strip('/') + '/'
        with os.scandir(real_path) as it:
            dir_list = [entry.name + ('/' if os.path.isdir(real_path + entry.name) else '') for entry in it]
            return json.dumps(dir_list)
    
    """
        Verification
    """
    
    def authenticate(self, connection_handler):
        request = connection_handler.request
        response = connection_handler.response
        
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
            response.update_header('WWW-Authenticate', 'Basic realm="Authorization Required"')
            raise HTTPStatusException(401)
        # return username and new cookie
        return (username, new_cookie)
            # if not authenicated, raise 401, no need to return
            # if authenicated, return (username, new_cookie); new_cookie is not None when authenicated by Authorization, otherwise None

    """
        Manipulations
    """
    
    # TODO: to be checked
    def mkdir(self, virtual_path):
        real_path = self.root_dir + virtual_path
        try:
            os.makedirs(real_path)
        except FileNotFoundError:
            raise HTTPStatusException(403) # TODO: 建立目录路径上存在同名文件导致建立失败会报这个错误，状态码待定
        except Exception:
            raise HTTPStatusException(500)
    
    # TODO: to be checked
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
                pass # TODO: 其它 MIME 类型，文档只要求支持 multipart/form-data，因为测试使用 requests
        if file_errer:
            raise HTTPStatusException(500)
        if not parsed:
            raise HTTPStatusException(400) # TODO: Content-Type is required
    
    # TODO: to be checked
    def delete_file(self, virtual_path):
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

