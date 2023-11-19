import sys
import argparse

from myhttp.server import HTTPSocketServer
from myhttp.logging import log_print, LogLevel


def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = 'localhost')
    argument_parser.add_argument('--port', '-p', type = int, default = 8080)
    return argument_parser.parse_args()


if __name__ == '__main__':
    args = cli_parser()
    
    try:
        server = HTTPSocketServer(args.ip, args.port)
        server.launch()
    except KeyboardInterrupt:
        log_print('Shutting down...', LogLevel.INFO)
        server.shutdown()
        log_print('Server is shut down', LogLevel.INFO)
        sys.exit(0)
    except:
        log_print(f'Unknown error', LogLevel.ERROR)
        sys.exit(1)

