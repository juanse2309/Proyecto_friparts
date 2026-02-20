import os
import jinja2

template_dir = 'frontend/templates'
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))

try:
    template = env.get_template('index.html')
    # Render with dummy data if necessary, but just parsing it first
    print("Template parsed successfully")
except Exception as e:
    print(f"Template error: {e}")
