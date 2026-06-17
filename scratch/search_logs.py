import os

base_dir = r"C:\Users\RYZEN\.gemini\antigravity\brain"
for folder in os.listdir(base_dir):
    log_path = os.path.join(base_dir, folder, ".system_generated", "logs", "overview.txt")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "liquidar_lote" in content:
            print(f"Found in folder: {folder}")
