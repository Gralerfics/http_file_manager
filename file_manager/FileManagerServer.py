import mimetypes
import threading
import pickle
import json
import time
import os

from myhttp.server import HTTPServer
from myhttp.exception import HTTPStatusException
from myhttp.content import HTTPResponseGenerator, HTTPHeaderUtils, HTMLUtils


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
        cookie = os.urandom(16).hex()
        while cookie in data:
            cookie = os.urandom(16).hex()
        data[cookie] = {'username': username, 'time_stamp': time_stamp, 'expire_time': expire_time, **extend_info}
        self._write(data)
        return cookie

    def remove(self, cookie):
        data = self._read()
        if cookie in data:
            del data[cookie]
            self._write(data)


"""
    FileManagerServer
        all the `path` (`<user>/<path>`) in this class is relative to `root_directory`
"""
class FileManagerServer(HTTPServer):
    root_dir = './data/'
    res_dir = './res/'
    reg_dir = './reg/'
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port)
        
        self.user_manager = UserManager(self.reg_dir + 'users.pkl')
        self.cookie_manager = CookieManager(self.reg_dir + 'cookies.pkl')
    
    """
        Information
    """
    
    def is_exist(self, virtual_path):
        real_path = self.root_dir + virtual_path
        return os.path.exists(real_path)
    
    def is_directory(self, virtual_path):
        real_path = self.root_dir + virtual_path
        return os.path.isdir(real_path)
    
    def is_file(self, virtual_path):
        real_path = self.root_dir + virtual_path
        return os.path.isfile(real_path)

    def belongs_to(self, virtual_path):
        if virtual_path == '':
            return None
        split = virtual_path.split('/')
        return split[0] if self.is_exist(split[0]) and self.is_directory(split[0]) else None
    
    def list_directory(self, path):
        real_path = self.root_dir + path
        with os.scandir(real_path) as it:
            return json.dumps([entry.name for entry in it])
    
    """
        Actions
    """
    
    def authenticate(self, request):
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
        # no cookie or cookie is invalid: check if there is valid authorization
        if not authenicated and request.headers.is_exist('Authorization'):
            username, password = HTTPHeaderUtils.parse_authorization_basic(request.headers.get('Authorization')) # parse authorization
            if username and password:
                if self.user_manager.authenticate(username, password):
                    new_cookie = self.cookie_manager.new(username, time.time_ns(), 10 * 1000 * 1000 * 1000)
                    authenicated = True
        # neither is valid
        if not authenicated:
            raise HTTPStatusException(401)
        # return
        return (username, new_cookie)
            # if not authenicated, raise 401, no need to return
            # if authenicated, return (username, new_cookie); new_cookie is not None when authenicated by Authorization
    
    def delete_file(self, virtual_path):
        real_path = self.root_dir + virtual_path
        os.remove(real_path)
    
    """
        Pages
    """
    
    def error_page(self, code, desc, request):
        # TODO: template
        response = HTTPResponseGenerator.text_html(
            body = f'<h1>{code} {desc}</h1>',
            version = request.request_line.version,
            status_code = code,
            status_desc = desc
        )
        if code == 401:
            response.headers.set('WWW-Authenticate', 'Basic realm="Authorization Required"')
        return response
    
    def directory_page(self, virtual_path):
        # TODO: template
            # 要求有 ./ ../ 和链接, 要有 400(?), 404(ok), 405(ok)
        
        with open(self.res_dir + 'html/get_directory.html', 'r') as f:
            page_content = f.read()
        page_content = HTMLUtils.render_template(page_content, {
            'path': virtual_path,
            'list_json': self.list_directory(virtual_path),
        })
        
        return page_content

