import mimetypes
import threading
import pickle
import json
import os

from myhttp.server import HTTPServer
from myhttp.message import HTTPResponseMessage
from myhttp.exception import HTTPStatusException
from myhttp.content import HTMLUtils
from myhttp.content import HTTPResponseGenerator


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
    
    def error_page(self, code, desc, request):
        # TODO: template
        response = HTTPResponseGenerator.text_html(
            f'<h1>{code} {desc}</h1>',
            version = request.request_line.version,
            status_code = code,
            status_desc = desc
        )
        if code == 401:
            response.headers.headers['WWW-Authenticate'] = 'Basic realm="Authorization Required"'
        return response
    
    def is_exist(self, path):
        real_path = self.root_dir + path
        return os.path.exists(real_path)
    
    def is_directory(self, path):
        real_path = self.root_dir + path
        return os.path.isdir(real_path)
    
    def is_file(self, path):
        real_path = self.root_dir + path
        return os.path.isfile(real_path)
    
    def list_directory(self, path):
        real_path = self.root_dir + path
        with os.scandir(real_path) as it:
            return json.dumps([entry.name for entry in it])
    
    def directory_page(self, path):
        with open(self.res_dir + 'html/directory.html', 'r') as f:
            page_content = f.read()
        page_content = HTMLUtils.render_template(page_content, {
            'path': path,
            'list_json': self.list_directory(path),
        })
        return page_content

