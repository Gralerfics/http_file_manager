import re

def parse_url(url):
    # 匹配目录和文件名
    path_pattern = re.compile(r'/([^/?]+)')
    path_matches = path_pattern.findall(url)

    # 匹配 GET 参数
    params_pattern = re.compile(r'\?([^/]+)')
    params_match = params_pattern.search(url)

    if params_match:
        # 如果有 GET 参数，解析成字典
        params_string = params_match.group(1)
        params_list = params_string.split('&')
        get_params = {param.split('=')[0]: param.split('=')[1] for param in params_list}
    else:
        # 如果没有 GET 参数，返回空字典
        get_params = {}

    return path_matches, get_params

# 测试例子
url1 = "/a.txt"
url2 = "/user/abc/a.html?abc=1&d=23"
url3 = "/"
url4 = "/backend_api/test_api"

result1 = parse_url(url1)
result2 = parse_url(url2)
result3 = parse_url(url3)
result4 = parse_url(url4)

print(result1)  # (['a.txt'], {})
print(result2)  # (['user', 'abc', 'a.html'], {'abc': '1', 'd': '23'})
print(result3)  # ([], {})
print(result4)  # (['backend_api', 'test_api'], {})

print('/'.join(result2[0]))  # user/abc/a.html
