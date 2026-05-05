import sys
import os

def purge_gsheets_routes(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith('@app.route'):
            # Check if this route uses gc.open_by_key
            j = i
            uses_gsheets = False
            route_block = []
            while j < len(lines):
                route_block.append(lines[j])
                if 'gc.open_by_key' in lines[j]:
                    uses_gsheets = True
                j += 1
                if j < len(lines) and (lines[j].strip().startswith('@app.route') or lines[j].strip().startswith('if __name__')):
                    break
            
            if uses_gsheets:
                new_lines.append(f"# [DELETED LEGACY GSHEETS ROUTE]\n")
                i = j
                continue
        
        new_lines.append(line)
        i += 1

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    purge_gsheets_routes('backend/app.py')
    print("Purge complete.")
