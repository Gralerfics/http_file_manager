import sys
import argparse

from myhttp.log import log_print, LogLevel
from file_manager import FileManagerServer


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
@server.error(pass_request = False)
def error_handler(code, desc):
    return server.error_page(code, desc)


@server.route('${path:d}', method = 'GET', pass_connection = True, pass_request = True, pass_uriparams = True)
def access_handler(connection, request, path, parameters = None):
    return server.error_page(200, 'ACCESSED')


# @server.route('/', pass_request = True)
# def index_page(request, parameters = None):
#     return server.index_page(request)


# @server.route('/${username}/${filepath:d}', pass_request = True, pass_uriparams = True)
# def request_file(request, username, filepath, parameters = None):
#     return server.request_file(username, filepath)


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

