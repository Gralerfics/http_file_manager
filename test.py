import re

class HTTPServer:
    def __init__(self):
        self.route_table = {}

    def route(self, path_pattern):
        def decorator(func):
            compiled_pattern = re.compile(self._convert_pattern(path_pattern))
            self.route_table[path_pattern] = (compiled_pattern, func)
            return func
        return decorator

    def _convert_pattern(self, path_pattern):
        # 实现你的 _convert_pattern 逻辑
        pass

    def handle_request(self, path):
        for pattern, func in self.route_table.values():
            match = pattern.match(path)
            if match:
                return func(**match.groupdict())
        return "404 Not Found"


class FileManagerServer:
    def __init__(self):
        self.server = HTTPServer()

    @HTTPServer.route("/${user1}/${dir1}")
    def test1(self, user1, dir1):
        return f"User: {user1}, Directory: {dir1}"

    @HTTPServer.route("/${user2}/${dir2}")
    def test2(self, user2, dir2):
        return f"User: {user2}, Directory: {dir2}"

# 示例
file_manager_server1 = FileManagerServer()
response1 = file_manager_server1.server.handle_request("/john/home1")
print(response1)  # Output: User: john, Directory: home1

file_manager_server2 = FileManagerServer()
response2 = file_manager_server2.server.handle_request("/mary/work2")
print(response2)  # Output: User: mary, Directory: work2
