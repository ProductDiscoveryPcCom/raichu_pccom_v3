"""
Tests del builder determinista de JSON-LD (utils/jsonld_builder.py).

Sin mocks: BeautifulSoup hace todo el trabajo. Cubre Article, FAQPage extraído
del <article class="contentGenerator__faqs">, Product opcional, y degradación
graceful con HTML malformado.
"""
from utils.jsonld_builder import build_article_jsonld


HTML_CON_FAQS = """
<article class="contentGenerator__main">
  <h2>Mejores PC gaming 2026</h2>
  <p>Análisis del mercado actual de PCs gaming...</p>
</article>
<article class="contentGenerator__faqs">
  <h3>¿Qué procesador es mejor para gaming en 2026?</h3>
  <p>Para gaming en 2026 lo ideal es un Ryzen 7 o Intel Core i5 de última generación.</p>
  <h3>¿Cuánta RAM necesita un PC gaming?</h3>
  <p>16GB es el mínimo recomendado; 32GB para juegos AAA modernos.</p>
  <h3>¿Vale la pena comprar SSD NVMe?</h3>
  <p>Sí, reduce los tiempos de carga drásticamente en juegos modernos.</p>
</article>
"""

HTML_SIN_FAQS = """
<article class="contentGenerator__main">
  <h1>Setup creativo profesional</h1>
  <p>Configuración para edición de video y 3D...</p>
</article>
"""


def test_extrae_headline_y_faqpage():
    out = build_article_jsonld(HTML_CON_FAQS, keyword="mejores pc gaming 2026")

    assert out["@context"] == "https://schema.org"
    graph = out["@graph"]
    article = next(b for b in graph if b["@type"] == "Article")
    assert article["headline"] == "Mejores PC gaming 2026"
    assert article["keywords"] == "mejores pc gaming 2026"

    faqpage = next(b for b in graph if b["@type"] == "FAQPage")
    assert len(faqpage["mainEntity"]) == 3
    q1 = faqpage["mainEntity"][0]
    assert q1["@type"] == "Question"
    assert q1["acceptedAnswer"]["@type"] == "Answer"
    assert "Ryzen" in q1["acceptedAnswer"]["text"]


def test_sin_faqs_devuelve_solo_article():
    out = build_article_jsonld(HTML_SIN_FAQS, keyword="setup creativo profesional")

    assert out["@type"] == "Article"
    assert "@graph" not in out
    assert out["headline"] == "Setup creativo profesional"


def test_incluye_meta_description_si_se_pasa():
    out = build_article_jsonld(
        HTML_SIN_FAQS,
        keyword="setup",
        meta_description="Descubre los mejores componentes para tu setup creativo.",
    )
    assert out["description"].startswith("Descubre")


def test_anade_bloque_product_si_se_pasan():
    products = [
        {
            "name": "Ryzen 7 7700X",
            "sku": "PCC-12345",
            "brand": "AMD",
            "url": "https://www.pccomponentes.com/ryzen-7-7700x",
            "price": 359.0,
        }
    ]
    out = build_article_jsonld(HTML_CON_FAQS, keyword="ryzen", products=products)

    graph = out["@graph"]
    product = next(b for b in graph if b["@type"] == "Product")
    assert product["name"] == "Ryzen 7 7700X"
    assert product["sku"] == "PCC-12345"
    assert product["brand"]["name"] == "AMD"
    assert product["offers"]["price"] == "359.0"
    assert product["offers"]["priceCurrency"] == "EUR"


def test_html_malformado_degrada_a_article_vacio():
    out = build_article_jsonld("<<< no es HTML >>>", keyword="x")

    assert out["@type"] == "Article"
    assert out["headline"] == ""
    assert out["keywords"] == "x"


def test_html_vacio_no_lanza():
    out = build_article_jsonld("", keyword="x")
    assert out["@type"] == "Article"
    assert out["headline"] == ""
