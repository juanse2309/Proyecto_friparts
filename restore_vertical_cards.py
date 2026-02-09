
import os

path = r"c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\static\css\mobile.css"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
for i, line in enumerate(lines):
    if "/* ===== MOBILE PRODUCT CARDS (CLIENT PORTAL) ===== */" in line:
        start_idx = i
        break

if start_idx != -1:
    # We replace from the comment to the end of the file since it's the last section usually
    # or we find the next major comment. Let's just take the rest of the file logic for now 
    # but more safely find the closing braces.
    
    replacement = [
        "/* ===== MOBILE PRODUCT CARDS (CLIENT PORTAL) ===== */\n",
        "@media (max-width: 768px) {\n",
        "    .product-grid-mobile {\n",
        "        display: grid;\n",
        "        grid-template-columns: 1fr;\n",
        "        gap: 20px;\n",
        "        padding: 15px;\n",
        "    }\n\n",
        "    .product-card-mobile {\n",
        "        background: white !important;\n",
        "        border-radius: 20px !important;\n",
        "        box-shadow: 0 10px 25px rgba(0,0,0,0.05) !important;\n",
        "        margin-bottom: 1rem !important;\n",
        "        padding: 20px !important;\n",
        "        display: flex !important;\n",
        "        flex-direction: column !important;\n",
        "        align-items: center !important;\n",
        "        gap: 12px !important;\n",
        "        border: 1px solid #edf2f7 !important;\n",
        "    }\n\n",
        "    .product-card-mobile .product-image {\n",
        "        width: 100% !important;\n",
        "        height: 180px !important;\n",
        "        max-width: 220px !important;\n",
        "        object-fit: contain !important;\n",
        "        background: #fff !important;\n",
        "        padding: 10px;\n",
        "        margin-bottom: 5px;\n",
        "    }\n\n",
        "    .product-card-mobile .product-info {\n",
        "        width: 100% !important;\n",
        "        display: flex !important;\n",
        "        flex-direction: column !important;\n",
        "        align-items: center !important;\n",
        "        text-align: center !important;\n",
        "        gap: 6px !important;\n",
        "    }\n\n",
        "    .product-card-mobile .product-name {\n",
        "        font-weight: 700 !important;\n",
        "        font-size: 1.1rem !important;\n",
        "        line-height: 1.2 !important;\n",
        "        color: #1e293b !important;\n",
        "        margin-bottom: 4px;\n",
        "    }\n\n",
        "    .product-card-mobile .product-code {\n",
        "        font-size: 0.85rem !important;\n",
        "        color: #64748b !important;\n",
        "        font-weight: 600;\n",
        "        background: #f1f5f9;\n",
        "        padding: 4px 12px;\n",
        "        border-radius: 50px;\n",
        "    }\n\n",
        "    .product-card-mobile .product-price {\n",
        "        font-size: 1.25rem !important;\n",
        "        font-weight: 800 !important;\n",
        "        color: var(--primary) !important;\n",
        "        margin: 8px 0 !important;\n",
        "    }\n\n",
        "    .product-card-mobile .quantity-selector {\n",
        "        display: flex !important;\n",
        "        align-items: center !important;\n",
        "        justify-content: center !important;\n",
        "        gap: 12px !important;\n",
        "        background: #f8fafc;\n",
        "        border-radius: 12px;\n",
        "        padding: 6px;\n",
        "        width: 100%;\n",
        "        max-width: 200px;\n",
        "        border: 1px solid #e2e8f0;\n",
        "    }\n\n",
        "    .product-card-mobile .quantity-selector button {\n",
        "        width: 40px !important;\n",
        "        height: 40px !important;\n",
        "        min-width: 40px !important;\n",
        "        border-radius: 10px !important;\n",
        "        display: flex !important;\n",
        "        align-items: center !important;\n",
        "        justify-content: center !important;\n",
        "        background: white;\n",
        "        border: 1px solid #e2e8f0;\n",
        "    }\n\n",
        "    .product-card-mobile .quantity-selector input {\n",
        "        width: 60px !important;\n",
        "        text-align: center !important;\n",
        "        font-weight: 800 !important;\n",
        "        font-size: 1.1rem !important;\n",
        "        border: none !important;\n",
        "        background: transparent !important;\n",
        "    }\n\n",
        "    .product-card-mobile .add-to-cart-btn {\n",
        "        width: 100% !important;\n",
        "        height: 50px !important;\n",
        "        border-radius: 12px !important;\n",
        "        background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%) !important;\n",
        "        color: white !important;\n",
        "        display: flex !important;\n",
        "        align-items: center !important;\n",
        "        justify-content: center !important;\n",
        "        font-weight: 700 !important;\n",
        "        font-size: 1rem !important;\n",
        "        box-shadow: 0 10px 15px -3px rgba(67, 97, 238, 0.3) !important;\n",
        "        margin-top: 10px !important;\n",
        "        border: none !important;\n",
        "        gap: 10px !important;\n",
        "    }\n\n",
        "    .friparts-banner {\n",
        "        max-height: 140px !important;\n",
        "        margin-bottom: 1.5rem !important;\n",
        "        border-radius: 20px;\n",
        "        overflow: hidden;\n",
        "    }\n\n",
        "    #portal-search {\n",
        "        font-size: 16px !important;\n",
        "        padding: 15px 20px !important;\n",
        "        border-radius: 15px !important;\n",
        "    }\n",
        "}\n"
    ]
    
    # Simple replacement of everything from start_idx onwards for this block
    # Note: This might overwrite anything after this block if there was something.
    # But usually this is at the end of the file.
    lines[start_idx:] = replacement
    
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Success")
else:
    print("Failed to find block")
