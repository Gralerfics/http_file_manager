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


@server.route('/upload', methods = ['POST', 'GET', 'HEAD']) # upload
def upload_handler(path, connection, request, parameters):
    if not request.request_line.method == 'POST':
        raise HTTPStatusException(405)
    
    # TODO: 上传文件, /upload?path=/<user>/...
        # 只能更改自己的目录，所以说根目录要求能 view 但不能改喽？
    pass


@server.route('/delete', methods = ['POST', 'GET', 'HEAD']) # delete
def upload_handler(path, connection, request, parameters):
    if not request.request_line.method == 'POST':
        raise HTTPStatusException(405)
    
    # TODO: 删除文件, /delete?path=/<user>/.../xxx.xxx
    pass


@server.route('/', methods = ['GET', 'HEAD']) # view and downloa # TODO: 似乎访问其它目录不需要 Authorization
def access_handler(path, connection, request, parameters):
    path_joined = '/'.join(path)
    username = path[0] if len(path) > 0 and server.is_exist(path_joined) and server.is_directory(path[0]) else None
    
    authenicated = False
    new_cookie = None

    # there is a cookie: check if it is valid
    if not authenicated and request.headers.is_exist('Cookie'):
        session_id = HTTPHeaderUtils.parse_cookie(request.headers.get('Cookie')) # psarse cookie
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
                    
    # no cookie or cookie is invalid: check if there is valid authorization
    if not authenicated and request.headers.is_exist('Authorization'):
        get_username, get_password = HTTPHeaderUtils.parse_authorization(request.headers.get('Authorization')) # parse authorization
        
        # TODO: 目前理解是如果用户名密码对了，但访问的目录没有权限，依然不会给 cookie
        if server.user_manager.authenticate(get_username, get_password) and (username is None or username == get_username):
            new_cookie = server.cookie_manager.new(get_username, time.time_ns(), 10 * 1000 * 1000 * 1000)
            authenicated = True
    
    # neither is valid
    if not authenicated:
        raise HTTPStatusException(401)
    
    # not found
    if not server.is_exist(path_joined):
        raise HTTPStatusException(404)
    
    # check if the path is a directory or a file
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
        raise HTTPStatusException(403) # TODO: 这是什么？会有这种情况吗？


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

