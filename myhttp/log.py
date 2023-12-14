from enum import Enum


class LogLevel(Enum):
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'


def log_print(message, level = LogLevel.INFO):
    if isinstance(level, LogLevel):
        print(f'[{level.value}] {message}')
    else:
        # if level == 'RAW_DATA': # TODO: log filters
        #     return
        print(f'[{level}] {message}')

