from backend.app import app
with app.app_context():
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, Path: {rule.rule}, Methods: {list(rule.methods)}")
