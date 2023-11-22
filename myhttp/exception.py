class ExceptionWithStatusCode(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


class HTTPStatusException(ExceptionWithStatusCode):
    status_description = {
        # 200: 'OK',
        # 206: 'Partial Content',
        301: 'Redirect',
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        416: 'Range Not Satisfiable',
        502: 'Bad Gateway',
        503: 'Service Temporarily Unavailable'
    }

