from myhttp.content import HTMLUtils
from . import FileManagerServer


"""
    Extended Variables:
        {{ file_manager_res_route }} -> server.res_route
        {{ file_manager_api_route }} -> server.api_route
        {{ file_manager_fetch_route }} -> server.fetch_route
        {{ file_manager_upload_route }} -> server.upload_route
        {{ file_manager_delete_route }} -> server.delete_route
    Usage:
        HTMLUtils.render_template(template, {
            'var': 'value',
            ...
            **get_file_manager_rendering_extended_variables(server)
        })
    大概就是所有请求的前端资源都会至少经过这些基本变量的渲染，用以保证前端可能使用到的 API 路径都是正确的（因为允许由用户修改各个 route 了）
"""
def get_file_manager_rendering_extended_variables(server: FileManagerServer):
    return {
        'file_manager_res_route': server.res_route,
        'file_manager_api_route': server.api_route,
        'file_manager_fetch_route': server.fetch_route,
        'file_manager_upload_route': server.upload_route,
        'file_manager_delete_route': server.delete_route
    }


"""
    Pages & Resources
"""

def get_error_page_rendered(code, desc, server: FileManagerServer):
    with open(server.res_dir + 'error_template.html', 'r') as f:
        page_content = f.read()
    
    return HTMLUtils.render_template(page_content, {
        'error_code': code,
        'error_desc': desc,
        **get_file_manager_rendering_extended_variables(server)
    })

