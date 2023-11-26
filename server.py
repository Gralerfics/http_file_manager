import sys
import argparse
import mimetypes

from myhttp.log import log_print, LogLevel
from file_manager import FileManagerServer

from myhttp.exception import HTTPStatusException
from myhttp.content import HTTPResponseGenerator


"""
    CLI Parser & Server Initialization
"""
def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = '0.0.0.0')
    argument_parser.add_argument('--port', '-p', type = int, default = 80)
    return argument_parser.parse_args()

args = cli_parser()
server = FileManagerServer(args.ip, args.port)

# TODO: to be removed
# server.cookie_manager._write({})


"""
    Routes
"""
@server.errorhandler(0)
def error_handler(code, desc, extend_headers, connection_handler):
    request = connection_handler.last_request
    connection_handler.send_response(HTTPResponseGenerator.by_content_type(
        body = server.error_page(code, desc),
        content_type = 'text/html',
        version = server.http_version if not request else request.request_line.version,
        status_code = code,
        status_desc = desc,
        extend_headers = extend_headers
    ))


@server.route('/frontend_res', methods = 'GET') # frontend_res (/frontend_res/<file_path>)
def resource_handler(path, parameters, connection_handler):
    request = connection_handler.last_request
    
    virtual_path = '/'.join(path)                                                       # target path (virtual)
    
    if not server.is_exist(virtual_path, resourse = True):                              # path not exist
        raise HTTPStatusException(404)

    if not server.is_file(virtual_path, resourse = True):                               # path is not a file
        raise HTTPStatusException(400)
    
    connection_handler.send_response(HTTPResponseGenerator.by_file_path(
        file_path = server.get_path(virtual_path, resourse = True),
        version = request.request_line.version
    ))


@server.route('/backend_api/user_register', methods = 'POST') # register (/backend_api/user_register)
def api_user_register(path, parameters, connection_handler):
    request = connection_handler.last_request
    
    if len(path) > 2:
        raise HTTPStatusException(400)
    
    # TODO: 后端 API 接口, POST, 注册用户
        # 注意用户不能叫 upload, delete, frontend_res, backend_api, etc.
    pass


@server.route('/upload', methods = ['POST', 'GET', 'HEAD']) # upload (/upload?path=/<user>/<dir_path>)
def upload_handler(path, parameters, connection_handler):
    request = connection_handler.last_request
    
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


@server.route('/delete', methods = ['POST', 'GET', 'HEAD']) # delete (/delete?path=/<user>/<file_or_dir_path>)
def upload_handler(path, parameters, connection_handler):
    request = connection_handler.last_request
    
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


@server.route('/', methods = ['GET', 'POST', 'HEAD']) # view and download
def access_handler(path, parameters, connection_handler):
    request = connection_handler.last_request
    
    if not request.request_line.method == 'GET':                                        # method should be GET
        raise HTTPStatusException(405)
    
    virtual_path = '/'.join(path)                                                       # target path (virtual)
    
    username, new_cookie = server.authenticate(connection_handler)                      # authenticate, TODO: 理解为虽然访问其它用户目录不需要验证，但无论如何必须处于登录状态
    extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
    
    if not server.is_exist(virtual_path):                                               # path not exist
        raise HTTPStatusException(404, extend_headers = extend_headers)
    
    if server.is_directory(virtual_path): # and path[-1] == '':                         # TODO: 这里关系到例如 localhost/user1/ 和 localhost/user1 的区别，目前是如果后者确实是目录，则忽略缺少斜杠的错误
        html_body = server.directory_page(virtual_path)
        connection_handler.send_response(HTTPResponseGenerator.by_content_type(
            body = html_body,
            content_type = 'text/html',
            version = request.request_line.version,
            extend_headers = extend_headers
        ), header_only = (request.request_line.method == 'HEAD'))
    elif server.is_file(virtual_path): # path[-1] != '':                                # TODO: 同前
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


"""
    Main
"""
if __name__ == '__main__':
    try:
        server.launch()
    except KeyboardInterrupt:
        log_print('Shutting down...', LogLevel.INFO)
        server.shutdown()
        log_print('Server is shut down', LogLevel.INFO)
        sys.exit(0)
    except:
        log_print(f'Unknown error', LogLevel.ERROR)
        raise
        # sys.exit(1)

