import argparse
from inspect import trace
import warnings
from shlex import split
from http.cookies import SimpleCookie
from urllib.parse import urlparse

from w3lib.http import basic_auth_header

from scrapy.utils.tracer import Tracer


class CurlParser(argparse.ArgumentParser):
    def error(self, message):
        error_msg = f'There was an error parsing the curl command: {message}'
        raise ValueError(error_msg)


curl_parser = CurlParser()
curl_parser.add_argument('url')
curl_parser.add_argument('-H', '--header', dest='headers', action='append')
curl_parser.add_argument('-X', '--request', dest='method')
curl_parser.add_argument('-d', '--data', '--data-raw', dest='data')
curl_parser.add_argument('-u', '--user', dest='auth')


safe_to_ignore_arguments = [
    ['--compressed'],
    # `--compressed` argument is not safe to ignore, but it's included here
    # because the `HttpCompressionMiddleware` is enabled by default
    ['-s', '--silent'],
    ['-v', '--verbose'],
    ['-#', '--progress-bar']
]

for argument in safe_to_ignore_arguments:
    curl_parser.add_argument(*argument, action='store_true')


def curl_to_request_kwargs(curl_command, ignore_unknown_options=True):
    """Convert a cURL command syntax to Request kwargs.

    :param str curl_command: string containing the curl command
    :param bool ignore_unknown_options: If true, only a warning is emitted when
                                        cURL options are unknown. Otherwise
                                        raises an error. (default: True)
    :return: dictionary of Request kwargs
    """

    tracer = Tracer()

    tracer.visited(1)

    curl_args = split(curl_command)

    if curl_args[0] != 'curl':
        tracer.visited(2)
        raise ValueError('A curl command must start with "curl"')
    else:
        tracer.visited(3)

    parsed_args, argv = curl_parser.parse_known_args(curl_args[1:])

    if argv:
        tracer.visited(4)
        msg = f'Unrecognized options: {", ".join(argv)}'
        if ignore_unknown_options:
            tracer.visited(5)
            warnings.warn(msg)
        else:
            tracer.visited(6)
            raise ValueError(msg)
    else:
        tracer.visited(7)

    url = parsed_args.url

    # curl automatically prepends 'http' if the scheme is missing, but Request
    # needs the scheme to work
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        tracer.visited(8)
        url = 'http://' + url
    else:
        tracer.visited(9)

    method = parsed_args.method or 'GET'

    result = {'method': method.upper(), 'url': url}

    headers = []
    cookies = {}
    for header in parsed_args.headers or ():
        tracer.visited(10)
        name, val = header.split(':', 1)
        name = name.strip()
        val = val.strip()
        if name.title() == 'Cookie':
            tracer.visited(11)
            for name, morsel in SimpleCookie(val).items():
                tracer.visited(12)
                cookies[name] = morsel.value
        else:
            tracer.visited(13)
            headers.append((name, val))

    if parsed_args.auth:
        tracer.visited(14)
        user, password = parsed_args.auth.split(':', 1)
        headers.append(('Authorization', basic_auth_header(user, password)))
    else:
        tracer.visited(15)

    if headers:
        tracer.visited(16)
        result['headers'] = headers
    else:
        tracer.visited(17)
    if cookies:
        tracer.visited(18)
        result['cookies'] = cookies
    else:
        tracer.visited(19)
    if parsed_args.data:
        tracer.visited(20)
        result['body'] = parsed_args.data
        if not parsed_args.method:
            tracer.visited(21)
            # if the "data" is specified but the "method" is not specified,
            # the default method is 'POST'
            result['method'] = 'POST'
        else:
            tracer.visited(22)
    else:
        tracer.visited(23)

    tracer.visited(24)

    return result
