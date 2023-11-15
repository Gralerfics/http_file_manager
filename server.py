import sys
import argparse
import socket


# ...


def launch(address, port):
    pass


def cli_parser():
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--ip', '-i', type = str, default = 'localhost')
    argument_parser.add_argument('--port', '-p', type = int, default = 8080)
    return argument_parser.parse_args()


if __name__ == '__main__':
    args = cli_parser()
    
    try:
        launch(args.ip, args.port)
    except KeyboardInterrupt:
        print('Server stopping...')
        sys.exit(0)

