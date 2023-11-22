import sys
import argparse

from myhttp.server import HTTPServer
from myhttp.log import log_print, LogLevel
from myhttp.request import HTTPRequestHandler


def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = '0.0.0.0')
    argument_parser.add_argument('--port', '-p', type = int, default = 80)
    return argument_parser.parse_args()


if __name__ == '__main__':
    args = cli_parser()
    
    try:
        server = HTTPServer(args.ip, args.port, HTTPRequestHandler)
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

