import sys
import argparse

from myhttp.server import HTTPConnectionHandler, EncryptedHTTPConnectionHandler
from myhttp.content import HTTPResponseGenerator
from myhttp.log import log_print, LogLevel
from file_manager import FileManagerServer


"""
    CLI Parser & Server Initialization
"""
def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = '0.0.0.0')
    argument_parser.add_argument('--port', '-p', type = int, default = 80)
    argument_parser.add_argument('--encrypted', '-e', type = bool, default = False)
    return argument_parser.parse_args()

args = cli_parser()
server = FileManagerServer(
    args.ip,
    args.port,
    ConnectionHandlerClass = HTTPConnectionHandler if not args.encrypted else EncryptedHTTPConnectionHandler,
    root_dir = './data/',
    reg_dir = './reg/',
    res_route = '/frontend_res',
    api_route = '/backend_api',
    fetch_route = '/',
    upload_route = '/upload',
    delete_route = '/delete'
)
# TODO: to be removed
server.cookie_manager._write({})


"""
    Error Handler
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

