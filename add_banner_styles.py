
css_content = """

/* ===== FRIPARTS CUSTOM BANNER ===== */
.friparts-banner {
    position: relative;
    width: 100%;
    max-width: 1200px; /* Limit width */
    margin: 0 auto 2rem auto; /* Center horizontally and add bottom margin */
    
    max-height: 250px;
    overflow: hidden; /* Ensure image doesn't overflow */
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
    background-color: #f8f9fa; /* Fallback background */
}

.friparts-banner .banner-image {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
    object-position: center;
}

.friparts-banner .banner-overlay {
    position: absolute;
    bottom: 20px;
    right: 30px;
    z-index: 10;
}

.friparts-banner .banner-overlay .btn {
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    background-color: white;
    color: #333;
    border: none;
}

.friparts-banner .banner-overlay .btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
    background-color: #f8f9fa;
}
"""

file_path = r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\static\css\styles.css'

try:
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(css_content)
    print("✅ Successfully appended banner styles to styles.css")
except Exception as e:
    print(f"❌ Error appending styles: {e}")
