#!/usr/bin/env python3
"""
Tests funcionales para validar las correcciones aplicadas.
VersiÃ³n exhaustiva: cada fix tiene mÃºltiples tests con casos edge.

Ejecutar: python -m pytest tests/test_fixes.py -v
"""

import importlib
import inspect
from pathlib import Path

import pytest


# ============================================================================
# GRUPO 1: FIX DEL NameError â€” logger no definido en ui/results.py
# ============================================================================

class TestResultsLoggerFix:
    """Valida que ui/results.py tiene logger correctamente definido."""

    def test_results_imports_logging(self):
        """results.py debe importar el mÃ³dulo logging."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "import logging" in source, "Falta 'import logging' en ui/results.py"

    def test_results_defines_logger(self):
        """results.py debe definir logger = logging.getLogger(__name__)."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "logger = logging.getLogger(__name__)" in source, \
            "Falta 'logger = logging.getLogger(__name__)' en ui/results.py"

    def test_logger_defined_before_first_use(self):
        """logger debe estar definido ANTES de su primer uso."""
        lines = Path("ui/results.py").read_text(encoding='utf-8').splitlines(keepends=True)
        logger_def_line = None
        logger_first_use = None
        for i, line in enumerate(lines, 1):
            if "logger = logging.getLogger" in line and logger_def_line is None:
                logger_def_line = i
            if "logger." in line and "logger = " not in line and logger_first_use is None:
                logger_first_use = i
        assert logger_def_line is not None, "No se encontrÃ³ definiciÃ³n de logger"
        assert logger_first_use is not None, "No se encontrÃ³ uso de logger"
        assert logger_def_line < logger_first_use, \
            f"logger se define en lÃ­nea {logger_def_line} pero se usa primero en lÃ­nea {logger_first_use}"

    def test_logger_usable_at_module_level(self):
        """Simular que logger es invocable sin error."""
        import logging
        logger = logging.getLogger("ui.results")
        # Estas llamadas NO deben lanzar excepciÃ³n
        logger.error("test error message")
        logger.warning("test warning message")
        logger.info("test info message")


# ============================================================================
# GRUPO 2: FIX del import path â€” from ui.media_shared â†’ from utils.media_shared
# ============================================================================

class TestMediaSharedImportPath:
    """Valida que el import de media_shared apunta al mÃ³dulo correcto."""

    def test_no_ui_media_shared_import(self):
        """No debe existir 'from ui.media_shared' en ningÃºn .py (excepto tests)."""
        import glob
        for pyfile in glob.glob("**/*.py", recursive=True):
            if "__pycache__" in pyfile or "test_" in pyfile:
                continue
            content = Path(pyfile).read_text(encoding='utf-8')
            assert "from ui.media_shared" not in content, \
                f"'{pyfile}' contiene 'from ui.media_shared' â€” debe ser 'from utils.media_shared'"

    def test_utils_media_shared_exists(self):
        """El fichero utils/media_shared.py debe existir."""
        assert Path("utils/media_shared.py").is_file(), \
            "utils/media_shared.py no existe"

    def test_ui_media_shared_does_not_exist(self):
        """El fichero ui/media_shared.py NO debe existir."""
        assert not Path("ui/media_shared.py").is_file(), \
            "ui/media_shared.py existe pero no deberÃ­a â€” el mÃ³dulo estÃ¡ en utils/"

    def test_media_shared_importable(self):
        """utils.media_shared debe ser importable sin error."""
        spec = importlib.util.find_spec("utils.media_shared")
        assert spec is not None, "utils.media_shared no es importable"

    def test_media_shared_exports_required_functions(self):
        """media_shared debe exportar render_image_generation_section y render_youtube_embed_section."""
        source = Path("utils/media_shared.py").read_text(encoding='utf-8')
        assert "def render_image_generation_section(" in source
        assert "def render_youtube_embed_section(" in source

    def test_results_has_integrated_multimedia(self):
        """v5.0: results.py tiene multimedia integrada (ya no importa media_shared)."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "def _render_multimedia_section" in source, \
            "results.py no contiene _render_multimedia_section integrada"
        assert "def _render_youtube_embed" in source, \
            "results.py no contiene _render_youtube_embed integrada"
        assert "def render_image_generation_tab" in source, \
            "results.py no contiene render_image_generation_tab"


# ============================================================================
# GRUPO 3: FIX de detecciÃ³n de grid en html_utils.py
# ============================================================================

class TestGridDetection:
    """Valida que validate_html_structure detecta grids correctamente."""

    def _validate(self, html):
        from utils.html_utils import validate_html_structure
        return validate_html_structure(html)

    def test_detects_grid_class(self):
        """Debe detectar class='grid'."""
        html = '<div class="grid cols-2"><div class="card">Test</div></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ class='grid'"

    def test_detects_grid_cols2(self):
        """Debe detectar cols-2."""
        html = '<div class="grid cols-2"><div>A</div><div>B</div></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ cols-2"

    def test_detects_grid_cols3(self):
        """Debe detectar cols-3."""
        html = '<div class="grid cols-3"><div>A</div></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ cols-3"

    def test_detects_grid_cols4(self):
        """Debe detectar cols-4."""
        html = '<div class="grid cols-4"><div>A</div></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ cols-4"

    def test_detects_mod_grid(self):
        """Debe detectar class='mod-grid'."""
        html = '<div class="mod-grid"><article class="mod-card">Test</article></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ mod-grid"

    def test_detects_vcard_grid(self):
        """Debe detectar class='vcard-grid'."""
        html = '<div class="vcard-grid"><article class="vcard">Test</article></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ vcard-grid"

    def test_detects_display_grid_css(self):
        """Debe detectar display:grid en CSS (caso legacy)."""
        html = '<style>.my-grid{display:grid;gap:16px;}</style><div class="my-grid">Test</div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ display:grid"

    def test_detects_display_grid_with_space(self):
        """Debe detectar display: grid con espacio."""
        html = '<style>.g{display: grid;}</style><div class="g">Test</div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ 'display: grid'"

    def test_no_false_positive_without_grid(self):
        """No debe dar falso positivo sin grid."""
        html = '<div class="container"><p>Simple text</p></div>'
        result = self._validate(html)
        assert result['has_grid'] is False, "Falso positivo: detectÃ³ grid donde no hay"

    def test_detects_grid_layout_legacy(self):
        """Debe seguir detectando grid-layout (legacy)."""
        html = '<div class="grid-layout"><div>A</div></div>'
        result = self._validate(html)
        assert result['has_grid'] is True, "No detectÃ³ grid-layout (legacy)"


# ============================================================================
# GRUPO 4: FIX de detecciÃ³n de TOC en html_utils.py
# ============================================================================

class TestTocDetection:
    """Valida que validate_html_structure detecta TOC correctamente."""

    def _validate(self, html):
        from utils.html_utils import validate_html_structure
        return validate_html_structure(html)

    def test_detects_toc_class_double_quotes(self):
        """Debe detectar class="toc"."""
        html = '<nav class="toc"><h4>En este artÃ­culo</h4></nav>'
        result = self._validate(html)
        assert result['has_toc'] is True, "No detectÃ³ class=\"toc\""

    def test_detects_toc_class_single_quotes(self):
        """Debe detectar class='toc'."""
        html = "<nav class='toc'><h4>Contenido</h4></nav>"
        result = self._validate(html)
        assert result['has_toc'] is True, "No detectÃ³ class='toc'"

    def test_detects_toc_with_additional_classes(self):
        """Debe detectar class="toc active" (toc con espacio y mÃ¡s clases)."""
        html = '<nav class="toc active"><h4>TOC</h4></nav>'
        result = self._validate(html)
        assert result['has_toc'] is True, "No detectÃ³ class='toc ' con clases adicionales"

    def test_detects_toc_bem_classes(self):
        """Debe detectar class="toc__title" (notaciÃ³n BEM)."""
        html = '<div class="toc__wrapper"><h4 class="toc__title">Contenido</h4></div>'
        result = self._validate(html)
        assert result['has_toc'] is True, "No detectÃ³ clases BEM de TOC"

    def test_no_false_positive_without_toc(self):
        """No debe dar falso positivo sin TOC."""
        html = '<div class="content"><p>Normal text</p></div>'
        result = self._validate(html)
        assert result['has_toc'] is False, "Falso positivo: detectÃ³ TOC donde no hay"


# ============================================================================
# GRUPO 5: FIX de detecciÃ³n de tablas en html_utils.py
# ============================================================================

class TestTableDetection:
    """Valida que validate_html_structure detecta tablas correctamente."""

    def _validate(self, html):
        from utils.html_utils import validate_html_structure
        return validate_html_structure(html)

    def test_detects_basic_table(self):
        """Debe detectar <table>...</table>."""
        html = '<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>'
        result = self._validate(html)
        assert result['has_table'] is True, "No detectÃ³ tabla bÃ¡sica"

    def test_detects_comparison_table(self):
        """Debe detectar comparison-table."""
        html = '<table class="comparison-table"><tr><th>Spec</th></tr></table>'
        result = self._validate(html)
        assert result['has_table'] is True, "No detectÃ³ comparison-table"

    def test_no_false_positive_without_closing_tag(self):
        """No debe detectar tabla si falta </table>."""
        html = '<p>Texto con <table en medio pero sin cerrar</p>'
        result = self._validate(html)
        assert result['has_table'] is False, "Falso positivo: detectÃ³ tabla sin cerrar"


# ============================================================================
# GRUPO 6: FIX de Gemini API key con Streamlit secrets fallback
# ============================================================================

class TestGeminiKeySecurity:
    """Valida que _get_gemini_client usa el nuevo patrÃ³n de seguridad (U1/F7)."""

    def test_source_imports_from_core_config(self):
        """image_gen.py debe importar la key desde core.config."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        assert "from core.config import GEMINI_API_KEY" in source, \
            "_get_gemini_client no usa el patrÃ³n de inyecciÃ³n directa desde core.config"

    def test_no_os_environ_bridge_leakage(self):
        """image_gen.py ya NO debe usar os.environ para la key."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        # Buscamos 'os.environ.get' especÃ­ficamente para GEMINI_API_KEY
        pattern = r"os\.environ\.get\(['\"]GEMINI_API_KEY['\"]"
        import re
        assert not re.search(pattern, source), \
            "_get_gemini_client sigue usando os.environ (vulnerabilidad U1)"

    def test_streamlit_secrets_fallback_maintained(self):
        """Debe mantener st.secrets como fallback final para compatibilidad Streamlit Cloud."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        assert "st.secrets" in source, \
            "Se eliminÃ³ el fallback de st.secrets en image_gen.py"

    def test_fallback_order_v5_security(self):
        """El orden ahora es: core.config (inyectado) â†’ st.secrets (fallback local)."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        idx_core = source.index("from core.config import GEMINI_API_KEY")
        idx_secrets = source.index("st.secrets.get('gemini_key'")
        assert idx_core < idx_secrets, \
            "El orden de fallback no prioriza la inyecciÃ³n directa de core.config"

    def test_function_preserves_original_params(self):
        """_get_gemini_client debe seguir devolviendo tuple (client|None, error_str)."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        # Verificar que devuelve None con mensaje de error en caso de no tener key
        assert 'return None, "GEMINI_API_KEY no configurada"' in source
        assert 'return None, "google-genai no instalado' in source


# ============================================================================
# GRUPO 7: FIX de error handling mejorado en results.py
# ============================================================================

class TestResultsErrorHandling:
    """Valida que el except en results.py muestra feedback al usuario."""

    def test_has_import_error_handler(self):
        """Debe tener except ImportError separado del genÃ©rico."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "except ImportError as e:" in source, \
            "Falta 'except ImportError as e:' en results.py"

    def test_has_generic_exception_handler(self):
        """Debe mantener except Exception genÃ©rico."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "except Exception as e:" in source, \
            "Falta 'except Exception as e:' en results.py"

    def test_import_error_shows_user_feedback(self):
        """ImportError debe mostrar algo al usuario (st.error, st.caption o st.warning)."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        idx_import = source.index("except ImportError")
        # Look for any user feedback in the next 200 chars
        block = source[idx_import:idx_import + 200]
        assert "st.caption" in block or "st.warning" in block or "st.error" in block, \
            "ImportError no muestra feedback al usuario"

    def test_generic_error_shows_user_feedback(self):
        """Exception genÃ©rica debe mostrar feedback al usuario (st.error o st.warning)."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        idx_generic = source.index("except Exception as e:")
        block = source[idx_generic:idx_generic + 200]
        assert "st.warning" in block or "st.error" in block, \
            "Exception genÃ©rica no muestra feedback al usuario"

    def test_import_error_before_generic(self):
        """except ImportError debe estar ANTES de except Exception en _execute_refinement."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        # Buscar dentro de _execute_refinement donde el patrÃ³n ImportErrorâ†’Exception es relevante
        refine_start = source.index("def _execute_refinement(")
        # Buscar el siguiente def para delimitar el bloque
        next_def = source.index("\ndef ", refine_start + 10)
        refine_block = source[refine_start:next_def]
        idx_import = refine_block.index("except ImportError")
        idx_generic = refine_block.index("except Exception")
        assert idx_import < idx_generic, \
            "except ImportError debe estar antes de except Exception en _execute_refinement"


# ============================================================================
# GRUPO 8: FIX de visual_elements en stage2 prompt
# ============================================================================

class TestStage2VisualElements:
    """Valida que build_new_content_correction_prompt_stage2 acepta visual_elements."""

    def test_stage2_accepts_visual_elements_param(self):
        """La funciÃ³n debe aceptar visual_elements como parÃ¡metro."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        sig = inspect.signature(build_new_content_correction_prompt_stage2)
        assert "visual_elements" in sig.parameters, \
            "build_new_content_correction_prompt_stage2 no acepta visual_elements"

    def test_stage2_visual_elements_has_default_none(self):
        """visual_elements debe tener default=None para retrocompatibilidad."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        sig = inspect.signature(build_new_content_correction_prompt_stage2)
        param = sig.parameters["visual_elements"]
        assert param.default is None, \
            f"visual_elements default es {param.default}, deberÃ­a ser None"

    def test_stage2_without_visual_elements_works(self):
        """Llamar sin visual_elements no debe lanzar error (retrocompat)."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        result = build_new_content_correction_prompt_stage2(
            draft_content="<style>:root{}</style><article>Test</article>",
            target_length=1500,
            keyword="test keyword"
        )
        assert isinstance(result, str)
        assert len(result) > 100

    def test_stage2_with_visual_elements_includes_them(self):
        """Con visual_elements, el prompt debe mencionarlos."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        result = build_new_content_correction_prompt_stage2(
            draft_content="<style>:root{}</style><article>Test</article>",
            target_length=1500,
            keyword="test keyword",
            visual_elements=["table", "grid", "callout"]
        )
        assert "table" in result
        assert "grid" in result
        assert "callout" in result
        assert "ELEMENTOS VISUALES" in result or "elementos visuales" in result.lower()

    def test_stage2_with_empty_visual_elements_no_section(self):
        """Con visual_elements=[] no debe aparecer secciÃ³n de visuales."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        result = build_new_content_correction_prompt_stage2(
            draft_content="<style>:root{}</style><article>Test</article>",
            target_length=1500,
            keyword="test keyword",
            visual_elements=[]
        )
        assert "ELEMENTOS VISUALES REQUERIDOS" not in result

    def test_stage2_alias_passes_visual_elements(self):
        """El alias build_correction_prompt_stage2 debe pasar visual_elements."""
        from prompts.new_content import build_correction_prompt_stage2
        result = build_correction_prompt_stage2(
            draft_content="<style>:root{}</style><article>Test</article>",
            target_length=1500,
            keyword="test",
            visual_elements=["comparison_table"]
        )
        assert "comparison_table" in result

    def test_stage2_preserves_all_original_params(self):
        """Todos los parÃ¡metros originales deben seguir presentes."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        sig = inspect.signature(build_new_content_correction_prompt_stage2)
        required_params = [
            "draft_content", "target_length", "keyword",
            "links_to_verify", "alternative_product", "products",
            "visual_elements"
        ]
        for p in required_params:
            assert p in sig.parameters, f"Falta parÃ¡metro '{p}' en stage2"


# ============================================================================
# GRUPO 9: FIX de visual_elements en stage3 prompt
# ============================================================================

class TestStage3VisualElements:
    """Valida que build_final_prompt_stage3 acepta visual_elements."""

    def test_stage3_accepts_visual_elements_param(self):
        """La funciÃ³n debe aceptar visual_elements como parÃ¡metro."""
        from prompts.new_content import build_final_prompt_stage3
        sig = inspect.signature(build_final_prompt_stage3)
        assert "visual_elements" in sig.parameters, \
            "build_final_prompt_stage3 no acepta visual_elements"

    def test_stage3_visual_elements_has_default_none(self):
        """visual_elements debe tener default=None."""
        from prompts.new_content import build_final_prompt_stage3
        sig = inspect.signature(build_final_prompt_stage3)
        param = sig.parameters["visual_elements"]
        assert param.default is None

    def test_stage3_without_visual_elements_works(self):
        """Llamar sin visual_elements no debe lanzar error."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<style>:root{}</style><article>Test</article>",
            analysis_feedback='{"puntuacion_general": 7}',
            keyword="test keyword",
            target_length=1500
        )
        assert isinstance(result, str)
        assert len(result) > 100

    def test_stage3_with_visual_elements_includes_reminder(self):
        """Con visual_elements, debe incluir recordatorio de mantenerlos."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<style>:root{}</style><article>Test</article>",
            analysis_feedback='{"puntuacion_general": 7}',
            keyword="test",
            target_length=1500,
            visual_elements=["table", "verdict", "grid"]
        )
        assert "table" in result
        assert "grid" in result
        assert "ELEMENTOS VISUALES" in result

    def test_stage3_with_visual_elements_gets_component_css(self):
        """Con visual_elements, el CSS del prompt debe incluir los componentes."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<style>:root{}</style><article>Test</article>",
            analysis_feedback="{}",
            keyword="test",
            target_length=1500,
            visual_elements=["table", "grid"]
        )
        # El CSS debe estar presente (al menos el fallback con table y grid)
        assert "<style>" in result.lower() or "table" in result

    def test_stage3_with_empty_visual_elements_no_reminder(self):
        """Con visual_elements=[] no debe incluir recordatorio."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<style>:root{}</style><article>Test</article>",
            analysis_feedback="{}",
            keyword="test",
            target_length=1500,
            visual_elements=[]
        )
        assert "ELEMENTOS VISUALES REQUERIDOS" not in result

    def test_stage3_preserves_all_original_params(self):
        """Todos los parÃ¡metros originales deben seguir presentes."""
        from prompts.new_content import build_final_prompt_stage3
        sig = inspect.signature(build_final_prompt_stage3)
        required_params = [
            "draft_content", "analysis_feedback", "keyword",
            "target_length", "links_data", "alternative_product",
            "products", "visual_elements"
        ]
        for p in required_params:
            assert p in sig.parameters, f"Falta parÃ¡metro '{p}' en stage3"

    def test_stage3_legacy_alias_still_works(self):
        """build_final_generation_prompt_stage3 debe seguir funcionando."""
        from prompts.new_content import build_final_generation_prompt_stage3
        result = build_final_generation_prompt_stage3(
            draft_content="<style>:root{}</style><article>Test</article>",
            corrections_json='{"puntuacion_general": 7}',
            target_length=1500
        )
        assert isinstance(result, str)
        assert len(result) > 100


# ============================================================================
# GRUPO 10: FIX de app.py â€” visual_elements pasado a stage2 y stage3
# ============================================================================

class TestAppVisualElementsPropagation:
    """Valida que el pipeline pasa visual_elements a las etapas 2 y 3 de forma defensiva.

    NOTA v5.1: La lÃ³gica de stage2/stage3 kwargs se moviÃ³ de app.py a core/pipeline.py.
    Los tests ahora validan el fichero correcto.
    """

    def _get_pipeline_source(self):
        return Path("core/pipeline.py").read_text(encoding='utf-8')

    def _extract_block(self, source, start_marker, end_marker):
        """Extrae bloque entre dos marcadores."""
        idx_start = source.index(start_marker)
        idx_end = source.index(end_marker, idx_start + len(start_marker))
        return source[idx_start:idx_end]

    def test_app_stage2_has_visual_elements_logic(self):
        """pipeline.py debe incluir lÃ³gica para pasar visual_elements a stage2."""
        source = self._get_pipeline_source()
        block = self._extract_block(source, "stage2_kwargs = dict(", "stage2_prompt = new_content")
        assert "visual_elements" in block, \
            "pipeline.py no tiene lÃ³gica de visual_elements para stage2"

    def test_app_stage3_has_visual_elements_logic(self):
        """pipeline.py debe incluir lÃ³gica para pasar visual_elements a stage3."""
        source = self._get_pipeline_source()
        block = self._extract_block(source, "stage3_kwargs = dict(", "stage3_prompt = new_content")
        assert "visual_elements" in block, \
            "pipeline.py no tiene lÃ³gica de visual_elements para stage3"

    def test_app_gets_visual_elements_from_config(self):
        """Debe obtener visual_elements de config.get('visual_elements', [])."""
        source = self._get_pipeline_source()
        assert "config.get('visual_elements', [])" in source, \
            "pipeline.py no lee visual_elements del config"

    def test_app_stage2_uses_inspect_for_safety(self):
        """stage2 debe usar inspect para verificar si el parÃ¡metro es soportado."""
        source = self._get_pipeline_source()
        block = self._extract_block(source, "stage2_kwargs = dict(", "stage2_prompt = new_content")
        assert "inspect.signature" in block, \
            "stage2 no usa inspect para verificar parÃ¡metros"

    def test_app_stage3_uses_inspect_for_safety(self):
        """stage3 debe usar inspect para verificar si el parÃ¡metro es soportado."""
        source = self._get_pipeline_source()
        block = self._extract_block(source, "stage3_kwargs = dict(", "stage3_prompt = new_content")
        assert "inspect.signature" in block, \
            "stage3 no usa inspect para verificar parÃ¡metros"

    def test_app_stage2_works_without_visual_elements_support(self):
        """
        Simula que build_new_content_correction_prompt_stage2 NO acepta visual_elements.
        La llamada no debe fallar.
        """
        import inspect as _inspect
        
        # Crear funciÃ³n mock SIN visual_elements
        def mock_stage2(draft_content, target_length=1500, keyword="",
                        links_to_verify=None, alternative_product=None, products=None):
            return f"PROMPT: {keyword}"
        
        # Simular la lÃ³gica de app.py
        stage2_kwargs = dict(
            draft_content="<article>Test</article>",
            target_length=1500,
            keyword="test",
            links_to_verify=[],
            alternative_product=None,
            products=[],
        )
        try:
            sig = _inspect.signature(mock_stage2)
            if 'visual_elements' in sig.parameters:
                stage2_kwargs['visual_elements'] = ['table']
        except Exception:
            pass
        
        # Esto NO debe lanzar TypeError
        result = mock_stage2(**stage2_kwargs)
        assert "test" in result

    def test_app_stage2_works_with_visual_elements_support(self):
        """
        Simula que build_new_content_correction_prompt_stage2 SÃ acepta visual_elements.
        Debe pasar el parÃ¡metro.
        """
        import inspect as _inspect
        
        # Crear funciÃ³n mock CON visual_elements
        def mock_stage2(draft_content, target_length=1500, keyword="",
                        links_to_verify=None, alternative_product=None, 
                        products=None, visual_elements=None):
            return f"PROMPT: {keyword} visual={visual_elements}"
        
        stage2_kwargs = dict(
            draft_content="<article>Test</article>",
            target_length=1500,
            keyword="test",
            links_to_verify=[],
            alternative_product=None,
            products=[],
        )
        try:
            sig = _inspect.signature(mock_stage2)
            if 'visual_elements' in sig.parameters:
                stage2_kwargs['visual_elements'] = ['table', 'grid']
        except Exception:
            pass
        
        result = mock_stage2(**stage2_kwargs)
        assert "table" in result and "grid" in result


# ============================================================================
# GRUPO 11: NO-REGRESSION â€” funciones originales intactas
# ============================================================================

class TestNoRegression:
    """Verifica que no se han eliminado funciones ni cambiado firmas incompatiblemente."""

    def test_results_has_all_original_functions(self):
        """results.py debe conservar todas las funciones originales."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        required_functions = [
            "def render_results_section(",
            "def render_content_tab(",
            "def render_analysis_tab(",
            "def render_validation_check(",
            "def render_structure_analysis(",
            "def _render_translation_section(",
        ]
        for func in required_functions:
            assert func in source, f"FunciÃ³n eliminada en results.py: {func}"

    def test_html_utils_has_all_original_functions(self):
        """html_utils.py debe conservar todas las funciones."""
        source = Path("utils/html_utils.py").read_text(encoding='utf-8')
        required = [
            "def count_words_in_html(",
            "def extract_content_structure(",
            "def validate_html_structure(",
            "def validate_cms_structure(",
            "def analyze_links(",
        ]
        for func in required:
            assert func in source, f"FunciÃ³n eliminada en html_utils.py: {func}"

    def test_image_gen_has_all_original_exports(self):
        """image_gen.py debe conservar todas las clases y funciones pÃºblicas."""
        source = Path("utils/image_gen.py").read_text(encoding='utf-8')
        required = [
            "class ImageType(",
            "class ImageRequest",  # dataclass
            "class GeneratedImage",  # dataclass
            "class ImageGenResult",  # dataclass
            "def is_gemini_available(",
            "def extract_headings_from_html(",
            "def generate_images(",
            "def create_images_zip(",
            "IMAGE_TYPE_LABELS",
        ]
        for item in required:
            assert item in source, f"Elemento eliminado en image_gen.py: {item}"

    def test_new_content_has_all_original_exports(self):
        """new_content.py debe conservar todas las funciones exportadas."""
        source = Path("prompts/new_content.py").read_text(encoding='utf-8')
        required = [
            "def build_new_content_prompt_stage1(",
            "def build_new_content_correction_prompt_stage2(",
            "def build_correction_prompt_stage2(",  # alias
            "def build_final_prompt_stage3(",
            "def build_final_generation_prompt_stage3(",  # alias
            "CSS_INLINE_MINIFIED",
        ]
        for item in required:
            assert item in source, f"Elemento eliminado en new_content.py: {item}"

    def test_app_has_all_core_functions(self):
        """app.py debe conservar funciones clave."""
        source = Path("app.py").read_text(encoding='utf-8')
        required = [
            "def main(",
            "def render_results(",
            "def execute_generation_pipeline(",
            "render_app_header",
            "def render_new_content_mode(",
            "def render_rewrite_mode(",
            "check_auth",
        ]
        for func in required:
            assert func in source, f"FunciÃ³n eliminada en app.py: {func}"

    def test_media_shared_has_all_functions(self):
        """media_shared.py debe conservar funciones pÃºblicas (v2.0: image redirect + youtube)."""
        source = Path("utils/media_shared.py").read_text(encoding='utf-8')
        required = [
            "def render_image_generation_section(",
            "def render_youtube_embed_section(",
        ]
        for func in required:
            assert func in source, f"FunciÃ³n eliminada en media_shared.py: {func}"


# ============================================================================
# GRUPO 12: CompilaciÃ³n de todos los archivos del proyecto
# ============================================================================

class TestCompilation:
    """Verifica que todos los archivos .py del proyecto compilan sin error."""

    def _compile_file(self, filepath):
        import py_compile
        try:
            py_compile.compile(filepath, doraise=True)
            return True, ""
        except py_compile.PyCompileError as e:
            return False, str(e)

    def test_compile_app(self):
        ok, err = self._compile_file("app.py")
        assert ok, f"app.py no compila: {err}"

    def test_compile_results(self):
        ok, err = self._compile_file("ui/results.py")
        assert ok, f"ui/results.py no compila: {err}"

    def test_compile_html_utils(self):
        ok, err = self._compile_file("utils/html_utils.py")
        assert ok, f"utils/html_utils.py no compila: {err}"

    def test_compile_image_gen(self):
        ok, err = self._compile_file("utils/image_gen.py")
        assert ok, f"utils/image_gen.py no compila: {err}"

    def test_compile_media_shared(self):
        ok, err = self._compile_file("utils/media_shared.py")
        assert ok, f"utils/media_shared.py no compila: {err}"

    def test_compile_new_content(self):
        ok, err = self._compile_file("prompts/new_content.py")
        assert ok, f"prompts/new_content.py no compila: {err}"

    def test_compile_all_py_files(self):
        """Compilar TODOS los .py del proyecto."""
        import glob
        failures = []
        for pyfile in sorted(glob.glob("**/*.py", recursive=True)):
            if "__pycache__" in pyfile or "test_" in pyfile:
                continue
            ok, err = self._compile_file(pyfile)
            if not ok:
                failures.append(f"{pyfile}: {err}")
        assert not failures, "Archivos que no compilan:\n" + "\n".join(failures)


# ============================================================================
# GRUPO 13: stage1 visual_elements â€” verificar que NO se rompiÃ³
# ============================================================================

class TestStage1VisualElementsIntact:
    """Verifica que stage1 sigue manejando visual_elements correctamente."""

    def test_stage1_accepts_visual_elements(self):
        """build_new_content_prompt_stage1 debe aceptar visual_elements."""
        from prompts.new_content import build_new_content_prompt_stage1
        sig = inspect.signature(build_new_content_prompt_stage1)
        assert "visual_elements" in sig.parameters

    def test_stage1_with_visual_elements_generates_instructions(self):
        """Con visual_elements, stage1 debe incluir instrucciones."""
        from prompts.new_content import build_new_content_prompt_stage1
        result = build_new_content_prompt_stage1(
            keyword="portÃ¡til gaming",
            arquetipo={'name': 'Review', 'description': 'Review de producto', 'tone': 'experto', 'structure': []},
            target_length=1500,
            visual_elements=["table", "grid", "verdict"]
        )
        assert "ELEMENTOS VISUALES" in result
        assert "table" in result.lower()
        assert "grid" in result.lower()


# ============================================================================
# GRUPO 14: Integridad de la cadena de renderizado
# ============================================================================

class TestRenderChainIntegrity:
    """Verifica que la cadena main â†’ render_results â†’ render_content_tab â†’ media estÃ¡ intacta."""

    def test_main_calls_render_results(self):
        """main() debe llamar a render_results()."""
        source = Path("app.py").read_text(encoding='utf-8')
        assert "render_results()" in source

    def test_refinement_in_results_not_app(self):
        """v5.0: refinamiento vive en results.py, no en app.py."""
        app_source = Path("app.py").read_text(encoding='utf-8')
        results_source = Path("ui/results.py").read_text(encoding='utf-8')
        assert "def render_refinement_section" not in app_source, \
            "Dead code: render_refinement_section aÃºn existe en app.py"
        assert "def _render_refinement_section" in results_source, \
            "results.py debe contener _render_refinement_section"

    def test_render_results_calls_render_results_section(self):
        """render_results() debe llamar a render_results_section()."""
        source = Path("app.py").read_text(encoding='utf-8')
        # Buscar dentro de render_results
        idx_start = source.index("def render_results()")
        idx_end = source.index("\ndef ", idx_start + 10)
        block = source[idx_start:idx_end]
        assert "render_results_section(" in block

    def test_render_results_section_calls_render_content_tab(self):
        """render_results_section debe llamar a render_content_tab."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        idx_start = source.index("def render_results_section(")
        idx_end = source.index("\ndef ", idx_start + 10)
        block = source[idx_start:idx_end]
        assert "render_content_tab(" in block

    def test_render_results_section_calls_multimedia(self):
        """v5.0: render_results_section debe llamar a _render_multimedia_section."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        idx_start = source.index("def render_results_section(")
        idx_end = source.index("\ndef ", idx_start + 10)
        block = source[idx_start:idx_end]
        assert "_render_multimedia_section(" in block, \
            "render_results_section debe llamar a _render_multimedia_section"

    def test_multimedia_section_has_images_and_youtube(self):
        """v5.0: _render_multimedia_section debe incluir imÃ¡genes y YouTube."""
        source = Path("ui/results.py").read_text(encoding='utf-8')
        idx_start = source.index("def _render_multimedia_section(")
        idx_end = source.index("\ndef ", idx_start + 10)
        block = source[idx_start:idx_end]
        assert "render_image_generation_tab(" in block, \
            "_render_multimedia_section debe llamar a render_image_generation_tab"
        assert "_render_youtube_embed(" in block, \
            "_render_multimedia_section debe llamar a _render_youtube_embed"


# ============================================================================
# GRUPO 15: Formato del prompt generado â€” integridad estructural
# ============================================================================

class TestPromptStructuralIntegrity:
    """Verifica que los prompts generados mantienen estructura vÃ¡lida."""

    def test_stage2_prompt_has_json_template(self):
        """Stage2 debe contener template JSON para la respuesta."""
        from prompts.new_content import build_new_content_correction_prompt_stage2
        result = build_new_content_correction_prompt_stage2(
            draft_content="<article>Test</article>",
            target_length=1500,
            keyword="test",
            visual_elements=["table"]
        )
        assert '"estructura"' in result
        assert '"tono"' in result
        assert '"problemas"' in result

    def test_stage3_prompt_has_html_structure(self):
        """Stage3 debe contener la estructura HTML requerida."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<article>Test</article>",
            analysis_feedback="{}",
            keyword="test",
            target_length=1500,
            visual_elements=["grid"]
        )
        assert "contentGenerator__main" in result
        assert "contentGenerator__faqs" in result
        assert "contentGenerator__verdict" in result
        assert "verdict-box" in result

    def test_stage3_prompt_no_double_css_section(self):
        """No debe haber dos secciones <style> en el template del prompt."""
        from prompts.new_content import build_final_prompt_stage3
        result = build_final_prompt_stage3(
            draft_content="<article>Test</article>",
            analysis_feedback="{}",
            keyword="test",
            target_length=1500,
            visual_elements=["table", "grid"]
        )
        # Solo debe haber una instrucciÃ³n de <style> en la estructura requerida
        count = result.count("ESTRUCTURA FINAL REQUERIDA")
        assert count == 1, f"Hay {count} secciones 'ESTRUCTURA FINAL REQUERIDA', deberÃ­a haber 1"


# ============================================================================
# GRUPO 16: SanitizaciÃ³n HTML con BeautifulSoup (U2)
# ============================================================================

class TestHTMLSanitization:
    """Valida la robustez de sanitize_html (U2)."""

    def test_strip_scripts(self):
        """Debe eliminar etiquetas <script> y su contenido."""
        from utils.html_utils import sanitize_html
        dirty = "<p>Texto</p><script>alert('hack');</script><div>MÃ¡s</div>"
        clean = sanitize_html(dirty)
        assert "<script>" not in clean
        assert "alert" not in clean
        assert "<p>Texto</p>" in clean
        assert "<div>MÃ¡s</div>" in clean

    def test_strip_iframes(self):
        """Debe eliminar etiquetas <iframe>."""
        from utils.html_utils import sanitize_html
        dirty = "<div><iframe src='malicious.com'></iframe></div>"
        clean = sanitize_html(dirty)
        assert "<iframe>" not in clean
        assert "malicious.com" not in clean

    def test_remove_event_handlers(self):
        """Debe eliminar atributos on* (onclick, onmouseover, etc.)."""
        from utils.html_utils import sanitize_html
        dirty = '<div onclick="doEvil()" onmouseover="steal()">Click</div>'
        clean = sanitize_html(dirty)
        assert "onclick" not in clean
        assert "onmouseover" not in clean
        assert "doEvil" not in clean
        assert "div" in clean

    def test_sanitize_javascript_links(self):
        """Debe neutralizar enlaces javascript:."""
        from utils.html_utils import sanitize_html
        dirty = '<a href="javascript:void(0)">Link</a>'
        clean = sanitize_html(dirty)
        assert 'href="#"' in clean
        assert "javascript" not in clean

    def test_preserve_styles(self):
        """Debe PRESERVAR etiquetas <style> necesarias para el Design System."""
        from utils.html_utils import sanitize_html
        dirty = "<style>.my-grid { color: red; }</style><article>Content</article>"
        clean = sanitize_html(dirty)
        assert "<style>" in clean
        assert ".my-grid" in clean
        assert "red" in clean

    def test_remove_other_dangerous_tags(self):
        """Debe eliminar object, embed, applet."""
        from utils.html_utils import sanitize_html
        dirty = "<object data='file.swf'></object><embed src='file.swf'>"
        clean = sanitize_html(dirty)
        assert "<object" not in clean
        assert "<embed" not in clean

    def test_pipeline_calls_sanitize(self):
        """pipeline.py debe contener llamadas a sanitize_html."""
        source = Path("core/pipeline.py").read_text(encoding='utf-8')
        assert "sanitize_html(" in source, \
            "Tarea U2 incompleta: sanitize_html no se llama en el pipeline"


# ============================================================================
# GRUPO 17: Token de seguridad en webhooks n8n (U3)
# ============================================================================

class TestN8NWebhookSecurity:
    """Valida que los webhooks n8n incluyen token de autenticaciÃ³n (U3)."""

    def test_config_exports_n8n_token(self):
        """core/config.py debe exportar N8N_API_TOKEN."""
        source = Path("core/config.py").read_text(encoding='utf-8')
        assert 'N8N_API_TOKEN' in source, \
            "core/config.py no define N8N_API_TOKEN"

    def test_n8n_imports_token_from_config(self):
        """n8n_integration.py debe importar N8N_API_TOKEN desde core.config."""
        source = Path("core/n8n_integration.py").read_text(encoding='utf-8')
        assert "from core.config import N8N_API_TOKEN" in source, \
            "n8n_integration.py no importa N8N_API_TOKEN de core.config"

    def test_bearer_header_injected_when_token_present(self):
        """Cuando N8N_API_TOKEN tiene valor, se debe incluir Authorization: Bearer."""
        source = Path("core/n8n_integration.py").read_text(encoding='utf-8')
        assert 'Authorization' in source, \
            "No se encontrÃ³ header Authorization en n8n_integration.py"
        assert 'Bearer' in source, \
            "No se encontrÃ³ formato Bearer en n8n_integration.py"

    def test_backward_compatible_without_token(self):
        """Sin token, el header Authorization no debe aÃ±adirse (if guard)."""
        source = Path("core/n8n_integration.py").read_text(encoding='utf-8')
        assert "if N8N_API_TOKEN:" in source, \
            "Falta guard condicional: token solo se aÃ±ade si existe"

    def test_token_not_leaked_in_logs(self):
        """El token NO debe aparecer en ningÃºn logger.info/debug/warning."""
        import re
        source = Path("core/n8n_integration.py").read_text(encoding='utf-8')
        log_calls = re.findall(r'logger\.\w+\(.*?\)', source, re.DOTALL)
        for call in log_calls:
            assert 'N8N_API_TOKEN' not in call, \
                f"Token potencialmente filtrado en log: {call[:80]}"
            assert 'Authorization' not in call, \
                f"Header Authorization potencialmente filtrado en log: {call[:80]}"
            assert 'Bearer' not in call, \
                f"Bearer token potencialmente filtrado en log: {call[:80]}"


# ============================================================================
# GRUPO 18: Fuentes autoritativas (I1)
# ============================================================================

class TestAuthoritativeSources:
    """Valida que las fuentes autoritativas se pasan y usan correctamente (I1)."""

    def test_form_data_has_authoritative_sources(self):
        """FormData debe incluir el campo authoritative_sources."""
        source = Path("ui/inputs.py").read_text(encoding='utf-8')
        assert 'authoritative_sources: Optional[str] = None' in source

    def test_ui_config_includes_authoritative_sources(self):
        """render_content_inputs debe incluir authoritative_sources en config."""
        source = Path("ui/inputs.py").read_text(encoding='utf-8')
        assert "'authoritative_sources': form_data.authoritative_sources or ''" in source

    def test_pipeline_passes_sources_to_stage1(self):
        """execute_generation_pipeline debe pasar fuentes a stage1."""
        source = Path("core/pipeline.py").read_text(encoding='utf-8')
        assert "authoritative_sources=config.get('authoritative_sources', '')" in source

    def test_prompt_stage1_includes_authoritative_sources_section(self):
        """build_new_content_prompt_stage1 debe generar sección de fuentes."""
        from prompts.new_content import build_new_content_prompt_stage1
        prompt = build_new_content_prompt_stage1(
            keyword="test",
            arquetipo={'name': 'Test'},
            authoritative_sources="https://fuente-oficial.com\nEspecificaciones de Marca"
        )
        assert "FUENTES AUTORITATIVAS" in prompt
        assert "https://fuente-oficial.com" in prompt
        assert "Especificaciones de Marca" in prompt
        assert "VERDAD ABSOLUTA" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

