import pandas as pd
import re
from difflib import get_close_matches
import os

class BOMNormalizer:
    def __init__(self, system_codes=None):
        self.system_codes = system_codes or []
        # Pre-compile regex for common prefixes
        self.code_pattern = re.compile(r'(?:FR-|IM-|MT-|CM-|CIM-)?([A-Z0-9.\-/]+)', re.IGNORECASE)

    def extract_base_code(self, long_name):
        """
        Attempts to extract the most 'code-like' part of a string.
        Example: 'FR-9430 A 9430 A BUJE' -> '9430 A'
        """
        if pd.isna(long_name): return ""
        s = str(long_name).strip().upper()
        
        # 1. Look for patterns like FR-XXXX or IM-XXXX
        # We also look for digits followed by A-Z (e.g. 9430 A)
        match = re.search(r'(?:FR-|IM-|MT-|CM-|CIM-)?([A-Z0-9]+(?:\s+[A-Z])?)', s)
        if match:
            code = match.group(1).strip().replace('-', ' ')
            # Clean up double spaces
            code = ' '.join(code.split())
            return code
            
        return s[:20] # Fallback to first characters

    def find_best_match(self, excel_name):
        """
        Finds the best matching system code using regex + fuzzy matching.
        """
        extracted = self.extract_base_code(excel_name)
        
        # If extracted matches exactly a system code
        if extracted in self.system_codes:
            return extracted, 1.0
            
        # Try finding the extracted code INSIDE a system code or vice-versa
        for code in self.system_codes:
            if extracted == code or (len(extracted) > 3 and extracted in code):
                return code, 0.95
        
        # Fuzzy matching as last resort
        close = get_close_matches(extracted, self.system_codes, n=1, cutoff=0.7)
        if close:
            return close[0], 0.8
            
        return None, 0.0

def run_normalization_test():
    print("🚀 Initializing BOM Normalizer...")
    
    # 1. Load System Codes from extracted GSheets CSVs
    try:
        df_fichas = pd.read_csv('current_fichas.csv')
        df_maestra = pd.read_csv('current_nueva_ficha_maestra.csv')
        
        # Unique IDs from both sources
        codes_1 = set(df_fichas['ID CODIGO'].dropna().astype(str).str.strip().str.upper())
        # Use SubProducto as the reference column in the new master sheet
        codes_2 = set(df_maestra['SubProducto'].dropna().astype(str).str.strip().str.upper())
        system_codes = list(codes_1.union(codes_2))
        print(f"✅ Loaded {len(system_codes)} unique system codes.")
    except Exception as e:
        print(f"⚠️ Warning: Could not load local system codes ({e}). Using mock sample.")
        system_codes = ['9430 A', '9430 B', '9430 C', '7025', 'BF-9735', 'AL-001', 'AL-002']

    normalizer = BOMNormalizer(system_codes)

    # 2. Load Excel
    df_new = pd.read_excel('Fichas tecnicas.xlsx', header=1)
    unique_excel_products = df_new['Producto'].dropna().unique()
    
    # 3. Process and Map
    mapping_results = []
    matched_count = 0
    total_count = len(unique_excel_products)
    
    print(f"\n📊 Processing {total_count} unique Excel products...")
    
    for name in unique_excel_products:
        # Ignore 'Total' rows
        if str(name).startswith('Total'): continue
        
        best_code, score = normalizer.find_best_match(name)
        if best_code:
            matched_count += 1
            mapping_results.append({
                'Excel Name': name[:50],
                'System Code': best_code,
                'Confidence': score
            })
        else:
            mapping_results.append({
                'Excel Name': name[:50],
                'System Code': 'NOT FOUND',
                'Confidence': 0.0
            })

    # 4. Display Results Sample
    df_map = pd.DataFrame(mapping_results)
    print("\n🔬 MAPPING SAMPLE (Top 15):")
    print(df_map.head(15).to_string(index=False))
    
    rate = (matched_count / total_count) * 100
    print(f"\n✅ TOTAL AUTO-MATCHING RATE: {rate:.2f}% ({matched_count}/{total_count})")
    
    # Save mapping for future use
    df_map.to_csv('mapping_results.csv', index=False)
    print("\n📂 Saved mapping result to: mapping_results.csv")

if __name__ == "__main__":
    run_normalization_test()
