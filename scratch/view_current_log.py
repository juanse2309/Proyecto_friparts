log_path = r"C:\Users\RYZEN\.gemini\antigravity\brain\c3fecdfe-8f1e-4581-8082-61c2bf24ec23\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    lines = f.readlines()
for line in lines[-50:]:
    print(line.strip())
