"""
Tests del barrido de enlaces internos existentes (modo Reescritura).

Cubre:
- Clasificación de URLs internas (classify_internal_link)
- Barrido + filtrado de internos + dedup (scan_existing_links)
- prepare_rewrite_config: preserved_links en config + dedup contra enlaces manuales
- Formatter del prompt (format_preserved_links_for_prompt)
- Inyección en el prompt de Stage 1 (build_rewrite_prompt_stage1)

Sin API keys: funciones puras (.claude/rules/tests.md).
"""

import pytest

from utils.html_utils import (
    classify_internal_link,
    scan_existing_links,
    _normalize_link_url,
)
from prompts.rewrite import (
    format_preserved_links_for_prompt,
    build_rewrite_prompt_stage1,
)
from ui.rewrite import prepare_rewrite_config


# ============================================================================
# CLASIFICACIÓN
# ============================================================================

class TestClassifyInternalLink:
    def test_blog(self):
        assert classify_internal_link("https://www.pccomponentes.com/blog/guia-gpu") == "blog"

    def test_pdp_producto_path(self):
        assert classify_internal_link("https://www.pccomponentes.com/producto/12345") == "pdp"

    def test_pdp_slug(self):
        assert classify_internal_link("https://www.pccomponentes.com/portatil-asus-rog") == "pdp"

    def test_plp_categoria_un_segmento(self):
        assert classify_internal_link("https://www.pccomponentes.com/perifericos") == "plp"

    def test_plp_categoria_dos_segmentos(self):
        assert classify_internal_link("https://www.pccomponentes.com/categoria/graficas") == "plp"

    def test_otro_home(self):
        assert classify_internal_link("https://www.pccomponentes.com/") == "otro"

    def test_otro_ancla(self):
        assert classify_internal_link("#faq") == "otro"

    def test_otro_busqueda(self):
        assert classify_internal_link("https://www.pccomponentes.com/?q=ratones") == "otro"

    def test_blog_gana_a_pdp_slug(self):
        # /blog/ tiene prioridad aunque la ruta contenga un slug tipo PDP
        assert classify_internal_link("https://www.pccomponentes.com/blog/mejor-monitor-gaming") == "blog"


# ============================================================================
# NORMALIZACIÓN
# ============================================================================

class TestNormalizeLinkUrl:
    def test_trailing_slash(self):
        a = _normalize_link_url("https://www.pccomponentes.com/perifericos/")
        b = _normalize_link_url("https://www.pccomponentes.com/perifericos")
        assert a == b

    def test_fragment_stripped(self):
        a = _normalize_link_url("https://www.pccomponentes.com/perifericos#top")
        b = _normalize_link_url("https://www.pccomponentes.com/perifericos")
        assert a == b

    def test_query_kept(self):
        a = _normalize_link_url("https://www.pccomponentes.com/buscar?q=raton")
        b = _normalize_link_url("https://www.pccomponentes.com/buscar?q=teclado")
        assert a != b

    def test_empty(self):
        assert _normalize_link_url("") == ""


# ============================================================================
# BARRIDO
# ============================================================================

class TestScanExistingLinks:
    def test_mixed_only_internal(self):
        html = (
            '<a href="https://www.pccomponentes.com/blog/guia-gpu">Guía GPU</a>'
            '<a href="https://www.pccomponentes.com/portatil-asus">Portátil</a>'
            '<a href="/perifericos">Periféricos</a>'
            '<a href="https://google.com">Externo</a>'
        )
        result = scan_existing_links(html)
        urls = [r["url"] for r in result]
        # El externo no aparece
        assert "https://google.com" not in urls
        assert len(result) == 3
        kinds = {r["url"]: r["kind"] for r in result}
        assert kinds["https://www.pccomponentes.com/blog/guia-gpu"] == "blog"
        assert kinds["https://www.pccomponentes.com/portatil-asus"] == "pdp"
        assert kinds["/perifericos"] == "plp"

    def test_anchor_cleaned(self):
        html = '<a href="/perifericos"><strong>Ver</strong> periféricos</a>'
        result = scan_existing_links(html)
        assert result[0]["anchor"] == "Ver periféricos"

    def test_dedup_trailing_slash_and_fragment(self):
        html = (
            '<a href="https://www.pccomponentes.com/perifericos">A</a>'
            '<a href="https://www.pccomponentes.com/perifericos/">B</a>'
            '<a href="https://www.pccomponentes.com/perifericos#top">C</a>'
        )
        result = scan_existing_links(html)
        assert len(result) == 1
        # Se conserva el primero
        assert result[0]["anchor"] == "A"

    def test_empty_html(self):
        assert scan_existing_links("") == []

    def test_malformed_html_graceful(self):
        # No debe lanzar; devuelve lo que pueda (posiblemente vacío)
        result = scan_existing_links("<a href=roto sin comillas>x</a> <div><a")
        assert isinstance(result, list)


# ============================================================================
# prepare_rewrite_config
# ============================================================================

def _call_prepare(preserved_links, posts_plps_links=None, rewrite_config=None):
    return prepare_rewrite_config(
        keyword="raton gaming",
        competitors_data=[],
        rewrite_config=rewrite_config,
        gsc_analysis=None,
        html_contents=rewrite_config["html_contents"],
        rewrite_mode="single",
        rewrite_instructions=rewrite_config["rewrite_instructions"],
        disambiguation_config=None,
        main_product_data=None,
        posts_plps_links=posts_plps_links or [],
        product_links=[],
        alternative_products=[],
        products=[],
        preserved_links=preserved_links,
    )


class TestPrepareRewriteConfig:
    def test_preserved_links_populated(self, rewrite_config):
        preserved = [
            {"url": "https://www.pccomponentes.com/blog/guia-gpu", "anchor": "Guía GPU", "kind": "blog"},
            {"url": "/perifericos", "anchor": "Periféricos", "kind": "plp"},
        ]
        config = _call_prepare(preserved, rewrite_config=rewrite_config)
        assert len(config["preserved_links"]) == 2
        assert config["preserved_links"][0]["type"] == "preserved"
        # No se vuelcan a links/enlaces unificados
        for l in config["links"]:
            assert l.get("type") != "preserved"

    def test_dedup_against_editorial(self, rewrite_config):
        shared = "https://www.pccomponentes.com/blog/guia-gpu"
        preserved = [{"url": shared, "anchor": "Guía (existente)", "kind": "blog"}]
        editorial = [{"url": shared, "anchor": "Guía (manual)"}]
        config = _call_prepare(preserved, posts_plps_links=editorial, rewrite_config=rewrite_config)
        # El preservado se descarta porque coincide con un editorial manual
        assert config["preserved_links"] == []
        assert len(config["editorial_links"]) == 1

    def test_dedup_internal_duplicates(self, rewrite_config):
        preserved = [
            {"url": "https://www.pccomponentes.com/perifericos", "anchor": "A", "kind": "plp"},
            {"url": "https://www.pccomponentes.com/perifericos/", "anchor": "B", "kind": "plp"},
        ]
        config = _call_prepare(preserved, rewrite_config=rewrite_config)
        assert len(config["preserved_links"]) == 1

    def test_empty_anchor_skipped(self, rewrite_config):
        preserved = [{"url": "/perifericos", "anchor": "", "kind": "plp"}]
        config = _call_prepare(preserved, rewrite_config=rewrite_config)
        assert config["preserved_links"] == []

    def test_none_preserved_links(self, rewrite_config):
        config = _call_prepare(None, rewrite_config=rewrite_config)
        assert config["preserved_links"] == []


# ============================================================================
# FORMATTER + INYECCIÓN EN PROMPT
# ============================================================================

class TestFormatPreservedLinks:
    def test_empty_returns_empty(self):
        assert format_preserved_links_for_prompt([]) == ""

    def test_includes_anchor_url_and_preserve_instruction(self):
        links = [{"url": "https://www.pccomponentes.com/perifericos", "anchor": "Periféricos", "kind": "plp"}]
        result = format_preserved_links_for_prompt(links)
        assert "Periféricos" in result
        assert "https://www.pccomponentes.com/perifericos" in result
        assert "PRESERVAR" in result


class TestPromptInjection:
    def test_stage1_includes_preserved_links(self, rewrite_config):
        rewrite_config["preserved_links"] = [
            {"url": "https://www.pccomponentes.com/blog/guia-gpu", "anchor": "Guía GPU", "kind": "blog"},
        ]
        prompt = build_rewrite_prompt_stage1(
            keyword="raton gaming",
            competitor_analysis="Análisis competencia.",
            config=rewrite_config,
        )
        assert "Guía GPU" in prompt
        assert "https://www.pccomponentes.com/blog/guia-gpu" in prompt
        assert "PRESERVAR" in prompt
