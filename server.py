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


# @server.route('/backend_api/directory_list', method = 'GET')
# def api_directory_list(complete_path, connection, request, parameters = None):
#     # TODO: authentication, 以及 401 和 404 哪个先？401 吧？
    
#     print(complete_path)
    
#     if not server.is_exist(complete_path):
#         raise HTTPStatusException(404)
    
#     body = server.directory_list(complete_path)
#     server.send_response(connection, HTTPResponseMessage.from_text(200, 'OK', body))


# # @server.route('/backend_api/user_register', method = 'POST', params = True)
# # def api_user_register(connection, request, parameters = None):
# #     print('register')
# #     pass


# @server.route('/', method = ['GET', 'HEAD'])
# def index_handler(connection, request, parameters = None):
#     body = server.directory_page('/')
#     server.send_response(connection, HTTPResponseMessage.from_text(200, 'OK', body))


# @server.route('/${user}/${path:d}', method = ['GET', 'HEAD'])
# def access_handler(user, path, connection, request, parameters = None):
#     # TODO: authentication, 以及 401 和 404 哪个先？401 吧？
    
#     complete_path = user + '/' + path
#     if not server.is_exist(complete_path):
#         raise HTTPStatusException(404)
    
#     if server.is_directory(complete_path):
#         body = server.directory_page(complete_path) if request.request_line.method == 'GET' else ''
#         server.send_response(connection, HTTPResponseMessage.from_text(200, 'OK', body))
#     elif server.is_file(complete_path):
#         pass # TODO
#     else:
#         raise HTTPStatusException(403) # TODO: 那是什么？会有这种情况吗？


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

