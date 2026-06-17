import json

log_path = r"C:\Users\RYZEN\.gemini\antigravity\brain\c3fecdfe-8f1e-4581-8082-61c2bf24ec23\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("type") == "USER_INPUT":
                print(f"--- USER INPUT ({data.get('created_at')}) ---")
                print(data.get("content"))
        except Exception as e:
            pass
