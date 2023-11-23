import sys
import argparse

from myhttp.server import HTTPServer
from myhttp.message import HTTPResponseMessage, HTTPStatusLine, HTTPHeaders
from myhttp.log import log_print, LogLevel


def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = '0.0.0.0')
    argument_parser.add_argument('--port', '-p', type = int, default = 80)
    return argument_parser.parse_args()


args = cli_parser()
server = HTTPServer(args.ip, args.port)


@server.route('/${username}/${directory:d}', pass_request = True, pass_uriparams = True)
def test_get(request, username, directory, parameters = None):
    body = f'User: {username}, Directory: {directory}, Parameters: {parameters}'.encode()
    return HTTPResponseMessage.text(200, 'OK', body)

@server.error
def error_handler(request, code, desc):
    return HTTPResponseMessage.text(200, 'OK', f'<h1>Error: {code} {desc}</h1>'.encode())


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

