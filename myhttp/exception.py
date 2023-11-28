class HTTPStatusException(Exception):
    default_status_description = {
        200: 'OK',
        206: 'Partial Content',
        301: 'Redirect',
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        416: 'Range Not Satisfiable',
        500: 'Internal Server Error', # TODO: not in the document
        502: 'Bad Gateway',
        503: 'Service Temporarily Unavailable'
    }
    
    def __init__(self, status_code, status_desc = None):
        self.status_code = status_code
        self.status_desc = status_desc if status_desc else self.default_status_description[status_code]

