import sys
import argparse

from myhttp.log import log_print, LogLevel
from file_manager import FileManagerServer

from myhttp.message import HTTPResponseMessage
from myhttp.exception import HTTPStatusException


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


"""
    Routes
"""
@server.errorhandler
def error_handler(code, desc, connection, request):
    server.send_response(connection, server.error_page(code, desc))


@server.route('/backend_api/list_directory', methods = 'GET')
def api_list_directory(path, connection, request, parameters):
    # TODO: authentication
    
    path_joined = '/'.join(path)
    print(path_joined)
    
    if not server.is_exist(path_joined):
        raise HTTPStatusException(404)
    
    if not server.is_directory(path_joined):
        raise HTTPStatusException(400) # the parameter `path` must be a directory
    
    result = server.list_directory(path_joined)
    server.send_response(connection, HTTPResponseMessage.from_text(200, 'OK', result))


@server.route('/', methods = ['GET', 'HEAD'])
def access_handler(path, connection, request, parameters):
    # TODO: authentication, 以及 401 和 404 哪个先？401 吧？
    
    path_joined = '/'.join(path)
    print(path_joined)
    
    if not server.is_exist(path_joined):
        raise HTTPStatusException(404)
    
    if server.is_directory(path_joined):
        html_body = server.directory_page(path_joined) if request.request_line.method == 'GET' else ''
        server.send_response(connection, HTTPResponseMessage.from_text(200, 'OK', html_body))
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

