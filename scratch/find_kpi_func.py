with open("backend/core/repository_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if line.strip().startswith("def "):
        print(f"Line {i+1}: {line.strip()}")
