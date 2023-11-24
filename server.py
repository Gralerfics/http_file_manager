import sys
import argparse

from myhttp.log import log_print, LogLevel
from file_manager import FileManagerServer

from myhttp.message import HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from myhttp.exception import HTTPStatusException
from myhttp.content import HTTPResponseGenerator, HTTPHeaderUtils


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
server.cookie_manager._write({})


"""
    Routes
"""
@server.errorhandler(0)
def error_handler(code, desc, connection, request):
    server.send_response(connection, server.error_page(code, desc, request))


@server.route('/frontend_res', methods = 'GET')
def resource_handler(path, connection, request, parameters):
    # 前端请求静态资源走这里，对应实际目录 ./res
        # 是否考虑加个 map 的注解……？
    pass


@server.route('/backend_api/user_register', methods = 'POST')
def api_user_register(path, connection, request, parameters):
    # TODO: 后端 API 接口, POST, 注册用户
        # 注意用户不能叫 upload, delete, frontend_res, backend_api, etc.
    pass


@server.route('/upload', methods = ['POST', 'GET', 'HEAD']) # upload (/upload?path=/<user>/<dir_path>)
def upload_handler(path, connection, request, parameters):
    if not request.request_line.method == 'POST':
        raise HTTPStatusException(405)
    
    # TODO: 需要检查 route（是否只有 upload） 和 path（参数是否存在等） 吗？
    if not parameters.__contains__('path'):
        raise HTTPStatusException(400)
    
    virtual_path = parameters['path'].strip('/')
    located_user = server.belongs_to(virtual_path)
    print(virtual_path)
    
    username, new_cookie = server.authenticate(request) # authenticate
    extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
    
    # TODO
    
    server.send_response(connection, HTTPResponseGenerator.text_html(version = request.request_line.version, extend_headers = extend_headers)) # 200 OK


@server.route('/delete', methods = ['POST', 'GET', 'HEAD']) # delete (/delete?path=/<user>/<file_path>)
def upload_handler(path, connection, request, parameters):
    if not request.request_line.method == 'POST':
        raise HTTPStatusException(405)
    
    # TODO: 需要检查 route（是否只有 delete） 和 path（参数是否存在等） 吗？
    if not parameters.__contains__('path'):
        raise HTTPStatusException(400)
    
    virtual_path = parameters['path'].strip('/')
    print(virtual_path)
    located_user = server.belongs_to(virtual_path)
    
    username, new_cookie = server.authenticate(request) # authenticate
    extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
    if username != located_user:
        raise HTTPStatusException(403)
    
    if not server.is_exist(virtual_path):
        raise HTTPStatusException(404)
    
    # TODO: 允许删目录吗？目前为不允许。
    if server.is_file(virtual_path):
        raise HTTPStatusException(403)
    
    server.delete_file(virtual_path)
    
    server.send_response(connection, HTTPResponseGenerator.text_html(version = request.request_line.version, extend_headers = extend_headers))


@server.route('/', methods = ['GET', 'HEAD']) # view and download
def access_handler(path, connection, request, parameters):
    virtual_path = '/'.join(path)
    
    # TODO: 理解为虽然访问其它用户目录不需要验证，但无论如何必须处于登录状态
    username, new_cookie = server.authenticate(request) # authenticate
    extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
    
    if not server.is_exist(virtual_path):
        raise HTTPStatusException(404)
    
    if server.is_directory(virtual_path):
        html_body = server.directory_page(virtual_path) if request.request_line.method == 'GET' else ''
        server.send_response(connection, HTTPResponseGenerator.text_html(body = html_body, version = request.request_line.version, extend_headers = extend_headers))
    else: # server.is_file(virtual_path):
        pass # TODO: file download


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

