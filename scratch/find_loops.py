with open("backend/routes/pulido_routes.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "for " in line or "while " in line:
        print(f"Line {i+1}: {line.strip()}")
