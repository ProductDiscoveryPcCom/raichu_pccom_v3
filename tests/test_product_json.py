"""Tests for utils/product_json_utils.py — P3.2 (total_comments propagation)
and P3.4 (specs table with >2 columns)."""

import json

from utils.product_json_utils import (
    _normalize_n8n_product,
    _parse_specifications,
    parse_product_json,
    parse_markdown_content,
)


# ── P3.4: tabla de especificaciones con >2 columnas ──────────────────────


class TestSpecsTableMultiColumn:
    def test_two_column_table_still_works(self):
        md = (
            "## ESPECIFICACIONES\n"
            "| Clave | Valor |\n"
            "|-------|-------|\n"
            "| RAM | 16GB |\n"
            "| CPU | i7 |\n"
        )
        specs = _parse_specifications(md)
        assert specs == {"RAM": "16GB", "CPU": "i7"}

    def test_three_column_table_joined(self):
        md = (
            "## ESPECIFICACIONES\n"
            "| Clave | Valor | Unidad |\n"
            "|-------|-------|--------|\n"
            "| RAM | 16 | GB |\n"
            "| Frecuencia | 3200 | MHz |\n"
        )
        specs = _parse_specifications(md)
        assert specs == {"RAM": "16 GB", "Frecuencia": "3200 MHz"}

    def test_four_column_table_joined(self):
        md = (
            "## ESPECIFICACIONES\n"
            "| Clave | Valor | Unidad | Nota |\n"
            "|-------|-------|--------|------|\n"
            "| Pantalla | 15.6 | pulgadas | IPS |\n"
        )
        specs = _parse_specifications(md)
        assert specs == {"Pantalla": "15.6 pulgadas IPS"}

    def test_three_column_with_empty_cells_skipped_in_join(self):
        md = (
            "## ESPECIFICACIONES\n"
            "| Clave | Valor | Unidad |\n"
            "|-------|-------|--------|\n"
            "| RAM | 16 |  |\n"
        )
        specs = _parse_specifications(md)
        # Cells vacías no introducen espacios extra
        assert specs == {"RAM": "16"}

    def test_header_row_skipped(self):
        md = (
            "## ESPECIFICACIONES\n"
            "| Clave | Valor |\n"
            "|-------|-------|\n"
        )
        assert _parse_specifications(md) == {}


# ── P3.2: total_comments propagado desde n8n ─────────────────────────────


class TestTotalCommentsPropagation:
    def _markdown_data_stub(self):
        return {
            "specifications": {},
            "characteristics": {},
            "summary": "",
            "description": "",
            "faqs": [],
            "advantages_list": [],
            "disadvantages_list": [],
            "advantages_text": "",
            "disadvantages_text": "",
            "rating": "",
            "price": "",
            "category": "",
            "product_url": "",
        }

    def test_snake_case_total_comments(self):
        raw = {
            "product_id": "123",
            "name": "Producto X",
            "brand": "BrandY",
            "family": "FamZ",
            "total_comments": 42,
            "markdown": "",
            "product_url": "https://example.com/x",
        }
        normalized = _normalize_n8n_product(raw, self._markdown_data_stub())
        assert normalized["totalComments"] == 42

    def test_camel_case_totalComments(self):
        raw = {
            "product_id": "123",
            "name": "Producto X",
            "brand": "BrandY",
            "family": "FamZ",
            "totalComments": 17,
            "markdown": "",
            "product_url": "https://example.com/x",
        }
        normalized = _normalize_n8n_product(raw, self._markdown_data_stub())
        assert normalized["totalComments"] == 17

    def test_snake_case_takes_precedence_over_camel(self):
        raw = {
            "product_id": "123",
            "name": "Producto X",
            "brand": "BrandY",
            "family": "FamZ",
            "total_comments": 99,
            "totalComments": 1,
            "markdown": "",
            "product_url": "https://example.com/x",
        }
        normalized = _normalize_n8n_product(raw, self._markdown_data_stub())
        assert normalized["totalComments"] == 99

    def test_missing_defaults_to_zero(self):
        raw = {
            "product_id": "123",
            "name": "Producto X",
            "brand": "BrandY",
            "family": "FamZ",
            "markdown": "",
            "product_url": "https://example.com/x",
        }
        normalized = _normalize_n8n_product(raw, self._markdown_data_stub())
        assert normalized["totalComments"] == 0

    def test_propagates_to_product_data_via_parse_product_json(self):
        n8n_payload = json.dumps([
            {
                "meta": [{"name": "products"}],
                "data": [
                    {
                        "product_id": "999",
                        "name": "Test Product",
                        "brand": "TestBrand",
                        "family": "TestFamily",
                        "total_comments": 128,
                        "markdown": "## DESCRIPCION\nLorem ipsum.\n",
                        "product_url": "https://example.com/test",
                    }
                ],
                "rows": 1,
            }
        ])
        product = parse_product_json(n8n_payload)
        assert product is not None
        assert product.total_comments == 128
        assert product.has_reviews is True
