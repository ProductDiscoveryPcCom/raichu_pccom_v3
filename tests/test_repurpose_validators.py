"""
Tests de los validadores del Repurposer (utils/repurpose_validators.py).
Funciones puras: sin mocks.
"""
from utils import repurpose_validators as v


# ---------- meta description ----------

def test_meta_description_ok():
    text = "Descubre los mejores PC gaming 2026 con un análisis completo de cada componente, precios actualizados y comparativa entre modelos. Encuentra el ideal."
    assert 140 <= len(text) <= 170, f"fixture mal calibrado ({len(text)} chars)"
    ok, errors, _ = v.validate_meta_description(text, keyword="pc gaming 2026")
    assert ok, errors


def test_meta_description_demasiado_corta():
    ok, errors, _ = v.validate_meta_description("Texto corto sobre PC gaming", keyword="pc gaming")
    assert not ok
    assert any("corta" in e.lower() for e in errors)


def test_meta_description_sin_keyword():
    text = "Descubre los mejores ordenadores del mercado con análisis de cada componente y precios actualizados. Compara modelos y elige el ideal."
    ok, errors, _ = v.validate_meta_description(text, keyword="pc gaming")
    assert not ok
    assert any("keyword" in e.lower() for e in errors)


def test_meta_description_con_emoji():
    text = "🚀 Descubre los mejores PC gaming 2026 con análisis de cada componente y precios actualizados. Compara modelos y elige el ideal."
    ok, errors, _ = v.validate_meta_description(text, keyword="pc gaming")
    assert not ok
    assert any("emoji" in e.lower() for e in errors)


# ---------- serp title ----------

def test_serp_title_ok():
    ok, errors, _ = v.validate_serp_title("PC Gaming 2026 | Comparativa PcComponentes", keyword="pc gaming")
    assert ok, errors


def test_serp_title_demasiado_largo():
    long_title = "PC Gaming 2026: la mejor comparativa de torres gaming actualizada al mes"
    ok, errors, _ = v.validate_serp_title(long_title, keyword="pc gaming")
    assert not ok


# ---------- rsa ----------

def test_rsa_ok():
    payload = {
        "titles": [f"Título {i:02d} PC" for i in range(15)],
        "descriptions": [f"Descripción {i} con detalle y CTA." for i in range(4)],
    }
    ok, errors, _ = v.validate_rsa(payload)
    assert ok, errors


def test_rsa_titulo_excede_30_chars():
    payload = {
        "titles": ["x" * 31] + [f"Ok {i}" for i in range(14)],
        "descriptions": ["abc"] * 4,
    }
    ok, errors, _ = v.validate_rsa(payload)
    assert not ok
    assert any("30 chars" in e for e in errors)


def test_rsa_duplicados():
    payload = {
        "titles": ["Dup"] * 15,
        "descriptions": ["abc"] * 4,
    }
    ok, errors, _ = v.validate_rsa(payload)
    assert not ok
    assert any("duplicados" in e for e in errors)


# ---------- x thread ----------

def test_x_thread_ok():
    payload = {"tweets": [{"n": i + 1, "text": f"Tweet {i} con valor."} for i in range(10)]}
    ok, errors, _ = v.validate_x_thread(payload)
    assert ok, errors


def test_x_thread_tweet_excede_280():
    payload = {"tweets": [{"n": i + 1, "text": "x" * 281 if i == 0 else f"T{i}"} for i in range(10)]}
    ok, errors, _ = v.validate_x_thread(payload)
    assert not ok
    assert any("280" in e for e in errors)


def test_x_thread_url_completa_warning_no_fail():
    payload = {"tweets": [{"n": i + 1, "text": "https://www.pccomponentes.com/pc-gaming"} for i in range(10)]}
    # warnings van en errors pero el ok depende solo de hard-fail (longitud > 280)
    ok, msgs, _ = v.validate_x_thread(payload)
    assert ok
    assert any("URL completa" in m for m in msgs)


def test_x_thread_demasiado_corto():
    payload = {"tweets": [{"n": i + 1, "text": "T"} for i in range(5)]}
    ok, errors, _ = v.validate_x_thread(payload)
    assert not ok


# ---------- newsletter ----------

def test_newsletter_ok():
    body = " ".join(["palabra"] * 60)
    payload = {"subject": "S", "preheader": "P", "body": body, "cta_text": "Ver más"}
    ok, errors, _ = v.validate_newsletter(payload)
    assert ok, errors


def test_newsletter_falta_campo():
    payload = {"subject": "S", "body": "x", "cta_text": "Y"}
    ok, errors, _ = v.validate_newsletter(payload)
    assert not ok
    assert any("preheader" in e for e in errors)


# ---------- linkedin carousel ----------

def test_linkedin_carousel_ok():
    payload = {"slides": [{"n": i + 1, "title": f"Slide {i}", "body_markdown": "..."} for i in range(6)]}
    ok, errors, _ = v.validate_linkedin_carousel(payload)
    assert ok, errors


def test_linkedin_carousel_pocos_slides():
    payload = {"slides": [{"n": 1, "title": "x"}, {"n": 2, "title": "y"}]}
    ok, errors, _ = v.validate_linkedin_carousel(payload)
    assert not ok


# ---------- featured snippet ----------

def test_featured_snippet_ok():
    answer = " ".join(["palabra"] * 50)
    payload = {"question": "¿Qué es?", "answer": answer}
    ok, errors, _ = v.validate_featured_snippet(payload)
    assert ok, errors


def test_featured_snippet_respuesta_corta():
    payload = {"question": "¿Qué es?", "answer": "Es algo."}
    ok, errors, _ = v.validate_featured_snippet(payload)
    assert not ok


# ---------- whatsapp ----------

def test_whatsapp_ok():
    ok, errors, _ = v.validate_whatsapp("📢 Mira nuestra nueva guía de PC gaming 2026 👉 {url}")
    assert ok, errors


# ---------- jsonld ----------

def test_jsonld_ok_con_faqpage():
    payload = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Article", "headline": "x"},
            {"@type": "FAQPage", "mainEntity": []},
        ],
    }
    ok, errors, _ = v.validate_jsonld(payload, expects_faqs=True)
    assert ok, errors


def test_jsonld_falta_faqpage_cuando_se_espera():
    payload = {"@context": "https://schema.org", "@type": "Article", "headline": "x"}
    ok, errors, _ = v.validate_jsonld(payload, expects_faqs=True)
    assert not ok
    assert any("FAQPage" in e for e in errors)


def test_jsonld_sin_context():
    payload = {"@type": "Article", "headline": "x"}
    ok, errors, _ = v.validate_jsonld(payload)
    assert not ok
