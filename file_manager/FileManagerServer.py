from myhttp.server import HTTPServer
from myhttp.message import HTTPResponseMessage
from myhttp.exception import HTTPStatusException


class FileManagerServer(HTTPServer):
    def index_page(self, request):
        return HTTPResponseMessage.text(200, 'OK', '<h1>Index Page</h1>'.encode())

    def request_file(self, username, filepath):
        # TODO: authorization
        body = f'User: {username}, File Path: {filepath}'.encode()
        return HTTPResponseMessage.text(200, 'OK', body)
    
    def error_handler(self, code, desc):
        return HTTPResponseMessage.text(200, 'OK', f'<h1>Error: {code} {desc}</h1>'.encode())

