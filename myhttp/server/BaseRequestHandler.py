# 实例化组合进 HTTPServer 对象，在其事件循环中调用，处理请求，发送响应
    # 借助 HTTPServer 获取请求、发送响应
    # 借助 HTTPMessage 解析请求、编码响应
    # Base 包含 xxx 功能（好像对请求和响应支持要求的不多，可能不需要再有更高级继承类了）
        # 具体功能实现也许再拆分到其它文件中（或者例如把功能做成类似 traits，做到 server（或 myhttp）以外的模块中，例如 mycookies，然后用户调用时组合进来）