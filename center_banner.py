
css_content = """

/* ===== FRIPARTS CUSTOM BANNER ===== */
.friparts-banner {
    position: relative;
    width: 100%;
    max-width: 1200px;
    margin: 0 auto 2rem auto;
    max-height: 250px;
    overflow: hidden;
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
    display: block;
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
}

.friparts-banner .banner-overlay .btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
}

/* Ajustes mobile dentro de styles.css para asegurar consistencia */
@media (max-width: 768px) {
    .friparts-banner {
        max-height: 150px;
        margin-bottom: 1rem;
    }
    .friparts-banner .banner-overlay {
        bottom: 10px;
        right: 15px;
    }
}
"""

with open(r'c:\Users\RYZEN\Documents\Proyectos de programacion\proyecto_bujes - copia\frontend\static\css\styles.css', 'a', encoding='utf-8') as f:
    f.write(css_content)

print("✅ Banner styles added and centered in styles.css")
