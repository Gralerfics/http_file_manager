import mimetypes
import threading
import pickle
import json
import os

from myhttp.server import HTTPServer
from myhttp.message import HTTPResponseMessage
from myhttp.exception import HTTPStatusException


class UserManager:
    def __init__(self):
        self.lock = threading.Lock()
    
    def read(self):
        self.lock.acquire()
        
        self.lock.release()
    
    def write(self, data):
        self.lock.acquire()
        
        self.lock.release()
    
    def register(self, username, password):
        pass
    
    def remove(self, username):
        pass
    
    def authenticate(self, username, password):
        pass


class CookieManager:
    def __init__(self):
        self.lock = threading.Lock()
    
    def read(self):
        self.lock.acquire()
        
        self.lock.release()
    
    def write(self, data):
        self.lock.acquire()
        
        self.lock.release()
    
    def get(self, cookie):
        pass
    
    def set(self, cookie):
        pass
    
    def remove(self, cookie):
        pass


"""
    FileManagerServer
        all the `path` (`<user>/<path>`) in this class is relative to `root_directory`
"""
class FileManagerServer(HTTPServer):
    root_directory = './data/'
    
    def __init__(self, hostname, port):
        super().__init__(hostname, port)
        
        self.user_manager = UserManager()
        self.cookie_manager = CookieManager()
    
    def error_page(self, code, desc):
        # TODO: template
        return HTTPResponseMessage.from_text(code, desc, f'<h1>Error: {code} {desc}</h1>')
    
    def is_exist(self, path):
        real_path = self.root_directory + path
        return os.path.exists(real_path)
    
    def is_directory(self, path):
        real_path = self.root_directory + path
        return os.path.isdir(real_path)
    
    def is_file(self, path):
        real_path = self.root_directory + path
        return os.path.isfile(real_path)
    
    def list_directory(self, path):
        real_path = self.root_directory + path
        with os.scandir(real_path) as it:
            return json.dumps([entry.name for entry in it])
    
    def directory_page(self, path):
        real_path = self.root_directory + path
        with open('./res/directory.html', 'r') as f:
            page_content = f.read()
        return page_content

