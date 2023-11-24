import sys
import argparse
import time

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
# server.user_manager.register('client1', '123')
# server.user_manager.register('client2', '234')
# server.user_manager.register('client3', '345')
print(server.user_manager._read())
print(server.cookie_manager._read())
# server.cookie_manager._write({})


"""
    Routes
"""
@server.errorhandler(0)
def error_handler(code, desc, connection, request):
    server.send_response(connection, server.error_page(code, desc, request))


@server.route('/frontend_res', methods = 'GET')
def resource_handler(path, connection, request, parameters):
    pass


@server.route('/', methods = ['GET', 'HEAD'])
def access_handler(path, connection, request, parameters):
    path_joined = '/'.join(path)
    username = path[0] if len(path) > 0 and server.is_exist(path_joined) and server.is_directory(path[0]) else None
    
    authenicated = False
    new_cookie = None

    # 有 Cookie 先看看有没有用
    if not authenicated and request.headers.headers.__contains__('Cookie'):
        session_id = HTTPHeaderUtils.parse_cookie(request.headers.headers['Cookie']) # parse cookie
        cookie_info = server.cookie_manager.get(session_id) # search cookie
        if cookie_info: # cookie exists
            get_username = cookie_info.get('username')
            time_stamp = cookie_info.get('time_stamp')
            expire_time = cookie_info.get('expire_time')
            if time_stamp + expire_time < time.time_ns():
                server.cookie_manager.remove(session_id) # timeout
            else:
                if username is None or get_username == username: # valid
                    authenicated = True
                    
    # Cookie 无效的话再看看 Authorization
    if not authenicated and request.headers.headers.__contains__('Authorization'):
        get_username, get_password = HTTPHeaderUtils.parse_authorization(request.headers.headers['Authorization']) # parse authorization
        
        # TODO: 目前理解是如果用户名密码对了，但访问的目录没有权限，依然不会给 cookie
        if server.user_manager.authenticate(get_username, get_password) and (username is None or username == get_username):
            new_cookie = server.cookie_manager.new(get_username, time.time_ns(), 10 * 1000 * 1000 * 1000)
            authenicated = True
            
    # 都没有，返回 401
    if not authenicated:
        raise HTTPStatusException(401)
    
    # 有权限，返回页面
    if not server.is_exist(path_joined):
        raise HTTPStatusException(404)
    
    if server.is_directory(path_joined):
        html_body = server.directory_page(path_joined) if request.request_line.method == 'GET' else ''
        server.send_response(connection, HTTPResponseGenerator.text_html(
            html_body,
            request.request_line.version,
            extend_headers = {'Set-Cookie': f'session-id={new_cookie}'} if new_cookie else {}
        ))
    elif server.is_file(path_joined):
        pass # TODO
    else:
        raise HTTPStatusException(403) # TODO: 那是什么？会有这种情况吗？


# @server.route('/backend_api/user_register', method = 'POST', params = True)
# def api_user_register(connection, request, parameters = None):
#     print('register')
#     pass


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

