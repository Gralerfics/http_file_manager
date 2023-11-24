import re

def parse_url(url):
    path_pattern = re.compile(r'^/?([^?]*)(\?.*)?$')
    params_pattern = re.compile(r'[\?&]([^=]+)=([^&]+)')
    
    # 匹配路径部分
    path_match = path_pattern.match(url)
    
    if path_match:
        # 提取路径和参数部分
        path = path_match.group(1)
        params_str = path_match.group(2)
        
        # 解析路径
        path_list = [segment for segment in path.split('/') if segment]
        
        # 解析参数
        params_dict = {}
        if params_str:
            params_list = params_pattern.findall(params_str)
            params_dict = dict(params_list)
        
        return path_list, params_dict
    else:
        return None

# 测试例子
url1 = "/upload?path=client1/dir/&c=3"
url2 = "a.txt"
url3 = "/user/abc/a.html?test=a/b/c"
url4 = "/"
url5 = "/test/?a=b&c=d"

print(parse_url(url1))  # (['upload'], {'path': 'client1/dir/', 'c': '3'})
print(parse_url(url2))  # (['a.txt'], {})
print(parse_url(url3))  # (['user', 'abc', 'a.html'], {'test': 'a/b/c'})
print(parse_url(url4))  # ([], {})
print(parse_url(url5))  # (['test'], {'a': 'b', 'c': 'd'})
