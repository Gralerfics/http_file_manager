import re


def render_template(template, variables = {}, pattern = r'{{\s*([^{}|]+)\s*(?:\|\s*safe\s*)?}}'):
    def replace(match):
        variable = match.group(1).strip()
        
        value = variables.get(variable, f'{{{{ {variable} }}}}')
        is_safe = '|safe' in match.group(0)
        if is_safe:
            value = str(value)
        
        return value
    
    pattern_compiled = re.compile(pattern)
    return pattern_compiled.sub(replace, template)

