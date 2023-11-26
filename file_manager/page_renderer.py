import os

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
"""
def get_file_manager_rendering_extended_variables(server: FileManagerServer):
    return {
        'file_manager_res_route': server.res_route,
        'file_manager_api_route': server.api_route,
        'file_manager_fetch_route': server.fetch_route,
        'file_manager_upload_route': server.upload_route,
        'file_manager_delete_route': server.delete_route
    }


def get_error_page_rendered(code, desc, server: FileManagerServer):
    with open(server.res_dir + 'error_template.html', 'r') as f:
        page_content = f.read()
    
    return HTMLUtils.render_template(page_content, {
        'error_code': code,
        'error_desc': desc,
        **get_file_manager_rendering_extended_variables(server)
    })


def get_directory_page_rendered(virtual_path, server: FileManagerServer):
    with open(server.res_dir + 'view_directory_template.html', 'r') as f:
        page_content = f.read()
    
    return HTMLUtils.render_template(page_content, {
        'virtual_path': virtual_path,
        'scan_list': server.list_directory(virtual_path),
        **get_file_manager_rendering_extended_variables(server)
    })

