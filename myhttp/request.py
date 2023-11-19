# import


class BaseRequestHandler:
    def __init__(self, request):
        self.request = request

    def handle(self):
        # to be overrided
        pass


# class HTTPRequestHandler:

# 实例化组合进 HTTPServer 对象，在其事件循环中调用，处理请求，发送响应
    # 借助 HTTPServer 获取请求、发送响应
    # 借助 HTTPMessage 解析请求、编码响应
    # 包含 xxx 功能（好像对请求和响应支持要求的不多，可能不需要再有更高级继承类了）
        # 具体功能实现也许再拆分到其它文件中（或者例如把功能做成类似 traits，做到 server（或 myhttp）以外的模块中，例如 mycookies，然后用户调用时组合进来）
        # or 只实现抽象接口，外面建个新包实现 file manager，在其内集成之
            # 这样还是不同于实际的服务器，so 还可以在方法实现内调用编写的网络应用，然后按 webapp 的开发方式写 file manager
        # 补充：http.server 包中的实现是在 SimpleHTTPRequestHandler 中的 do_GET 等方法中调用的，也就是写死的，其它功能是再次继承来实现的，例如 CGIHTTPRequestHandler