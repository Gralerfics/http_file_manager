from myhttp.server import HTTPServer
from myhttp.message import HTTPResponseMessage
from myhttp.exception import HTTPStatusException


class FileManagerServer(HTTPServer):
    def error_page(self, code, desc):
        return HTTPResponseMessage.from_text(code, desc, f'<h1>Error: {code} {desc}</h1>')
    
    def access_directory(self, path):
        
        pass
    
    def access_file(self, file):
        
        pass

