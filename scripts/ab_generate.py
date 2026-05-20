"""
Generador A/B headless para validación Fase 4.

Llama directo a ContentGenerator + prompts/new_content sin Streamlit.
Itera N keywords × M generaciones y vuelca HTMLs a disco.

Uso:
    # En cada rama por separado (main, luego phase4-prompts):
    python scripts/ab_generate.py --out docs/validation/htmls/baseline
    python scripts/ab_generate.py --out docs/validation/htmls/modified

    # Sólo una keyword (debug):
    python scripts/ab_generate.py --out tmp/ --keywords arq04-review

    # Sin OpenAI dual (ahorro ~30%):
    python scripts/ab_generate.py --out docs/validation/htmls/baseline --no-openai

API keys: lee ANTHROPIC_API_KEY y OPENAI_API_KEY del entorno o de
.streamlit/secrets.toml (claves 'claude_key' / 'openai_key').
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ab_generate")


KEYWORDS = [
    # (subdir, keyword, arquetipo_code, target_length, has_reviews)
    ("arq07-ranking",   "mejores portatiles gaming",       "ARQ-7",  1800, True),
    ("arq04-review",    "review iphone 15 pro",            "ARQ-4",  1600, False),
    ("arq03-educativo", "que es ddr5",                     "ARQ-3",  1400, False),
    ("arq20-bf",        "ofertas black friday portatiles", "ARQ-20", 1600, True),
    ("arq13-setup",     "como montar pc gaming",           "ARQ-13", 1800, False),
]


def load_secrets_into_env() -> None:
    """Carga claves desde .streamlit/secrets.toml a os.environ si no están ya."""
    if os.getenv("ANTHROPIC_API_KEY") and os.getenv("OPENAI_API_KEY"):
        return
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return
    try:
        import tomllib  # py311+
    except ImportError:
        import tomli as tomllib  # type: ignore
    data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
    if not os.getenv("ANTHROPIC_API_KEY") and data.get("claude_key"):
        os.environ["ANTHROPIC_API_KEY"] = data["claude_key"]
    if not os.getenv("OPENAI_API_KEY") and data.get("openai_key"):
        os.environ["OPENAI_API_KEY"] = data["openai_key"]


def extract_html(text: str) -> str:
    """Extrae el HTML completo del response (entre el primer <article> y el último </article>).

    Si el modelo lo envuelve en ```html ... ```, lo limpia primero.
    """
    if not text:
        return ""
    m = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1)
    # quedarse desde la primera <article hasta la última </article>
    start = text.find("<article")
    end = text.rfind("</article>")
    if start != -1 and end != -1:
        return text[start : end + len("</article>")]
    return text.strip()


def generate_one(
    *,
    generator,
    keyword: str,
    arquetipo: dict,
    target_length: int,
    use_openai: bool,
) -> tuple[str, dict]:
    """Ejecuta las 3 etapas y devuelve (HTML final, telemetría CMS).

    Tras Stage 3 mide el cumplimiento CRUDO de la estructura CMS (efecto Capa A,
    comparable con el baseline antiguo) y aplica la Capa C real (backstop puro
    importado de utils.html_utils) para garantizar los 3 <article>.

    NOTA: la Capa B (reparación LLM dirigida) NO se ejecuta aquí — vive en
    core/pipeline.py acoplada a Streamlit. En producción se ejecuta ENTRE Stage 3
    y la Capa C, así que el nº de backstops/verdicts-fabricados medido aquí es una
    COTA SUPERIOR: producción será igual o mejor.
    """
    from prompts.new_content import (
        build_new_content_prompt_stage1,
        build_new_content_correction_prompt_stage2,
        build_final_prompt_stage3,
    )
    from prompts.brand_tone import get_system_prompt_base

    system_prompt = get_system_prompt_base()

    # Stage 1 — draft
    p1 = build_new_content_prompt_stage1(
        keyword=keyword,
        arquetipo=arquetipo,
        target_length=target_length,
    )
    log.info("  Stage 1 (draft) keyword=%r prompt_chars=%d", keyword, len(p1))
    t0 = time.time()
    r1 = generator.generate(prompt=p1, system_prompt=system_prompt)
    if not r1.success or not r1.content:
        raise RuntimeError(f"Stage 1 failed: {getattr(r1, 'error', 'unknown')}")
    draft = extract_html(r1.content) or r1.content
    log.info("  Stage 1 done in %.1fs, chars=%d", time.time() - t0, len(draft))

    # Stage 2 — Claude analysis
    p2 = build_new_content_correction_prompt_stage2(
        draft_content=draft,
        target_length=target_length,
        keyword=keyword,
        arquetipo_code=arquetipo.get("code", ""),
        arquetipo_structure=arquetipo.get("structure"),
    )
    log.info("  Stage 2 (Claude analysis) prompt_chars=%d", len(p2))
    t0 = time.time()
    r2 = generator.generate(prompt=p2, system_prompt=system_prompt)
    if not r2.success or not r2.content:
        raise RuntimeError(f"Stage 2 (Claude) failed: {getattr(r2, 'error', 'unknown')}")
    claude_analysis = r2.content
    log.info("  Stage 2 (Claude) done in %.1fs, chars=%d", time.time() - t0, len(claude_analysis))

    # Stage 2 dual — OpenAI analysis (opcional)
    openai_analysis = ""
    if use_openai and os.getenv("OPENAI_API_KEY"):
        try:
            from core.openai_client import call_openai_api
            t0 = time.time()
            r2b = call_openai_api(prompt=p2, system_prompt=system_prompt)
            if r2b and getattr(r2b, "content", ""):
                openai_analysis = r2b.content
                log.info("  Stage 2 (OpenAI) done in %.1fs, chars=%d", time.time() - t0, len(openai_analysis))
        except Exception as e:
            log.warning("  OpenAI analysis falló (continuo sin él): %s", e)

    if openai_analysis:
        analysis_feedback = (
            "=== Análisis Claude ===\n" + claude_analysis +
            "\n\n=== Análisis OpenAI (validación independiente) ===\n" + openai_analysis
        )
    else:
        analysis_feedback = claude_analysis

    # Stage 3 — final (C4: pasar arquetipo_code para que dispare la directiva
    # de preservación de mini-stories en arquetipos del miniset).
    # inspect.signature → solo lo pasa si el builder lo acepta, de modo que el
    # mismo script corre en main (sin el param) y en phase4-prompts (con él).
    import inspect
    s3_kwargs = dict(
        draft_content=draft,
        analysis_feedback=analysis_feedback,
        keyword=keyword,
        target_length=target_length,
    )
    if "arquetipo_code" in inspect.signature(build_final_prompt_stage3).parameters:
        s3_kwargs["arquetipo_code"] = arquetipo.get("code", "")
    p3 = build_final_prompt_stage3(**s3_kwargs)
    log.info("  Stage 3 (final) prompt_chars=%d", len(p3))
    t0 = time.time()
    r3 = generator.generate(prompt=p3, system_prompt=system_prompt)
    if not r3.success or not r3.content:
        raise RuntimeError(f"Stage 3 failed: {getattr(r3, 'error', 'unknown')}")
    final_html = extract_html(r3.content) or r3.content
    log.info("  Stage 3 done in %.1fs, chars=%d", time.time() - t0, len(final_html))

    # --- Determinismo CMS: medir Capa A cruda + aplicar Capa C real ---
    # validate_cms_articles existe en ambas ramas; inject_missing_cms_articles
    # SOLO en phase4-prompts. En main → backstop_available=False y NO se inyecta
    # (baseline = salida cruda real de main, sin garantía).
    from utils.html_utils import validate_cms_articles
    try:
        from utils.html_utils import inject_missing_cms_articles, _extract_verdict_paragraph
        _backstop_available = True
    except ImportError:
        inject_missing_cms_articles = None
        _extract_verdict_paragraph = None
        _backstop_available = False

    check = validate_cms_articles(final_html)
    missing_after_stage3 = list(check["missing"])
    verdict_fabricated = (
        _backstop_available
        and "contentGenerator__verdict" in missing_after_stage3
        and _extract_verdict_paragraph(final_html) is None
    )
    if missing_after_stage3 and _backstop_available:
        final_html = inject_missing_cms_articles(
            final_html, missing_after_stage3, keyword=keyword, faq_questions=None
        )
        log.warning(
            "  CMS backstop (Capa C) aplicado: faltaban %s%s",
            missing_after_stage3,
            " [VERDICT FABRICADO DESDE CERO]" if verdict_fabricated else "",
        )
    elif missing_after_stage3:
        log.warning("  Faltan articles %s y no hay backstop en esta rama (baseline crudo)",
                    missing_after_stage3)
    final_check = validate_cms_articles(final_html)

    meta = {
        "keyword": keyword,
        "arquetipo_code": arquetipo.get("code", ""),
        "backstop_available": _backstop_available,
        "stage3_all_present": check["all_present"],          # Capa A sola
        "missing_after_stage3": missing_after_stage3,
        "capa_c_fired": bool(missing_after_stage3) and _backstop_available,
        "classes_backstopped": missing_after_stage3 if _backstop_available else [],
        "verdict_fabricated": verdict_fabricated,
        "final_all_present": final_check["all_present"],     # True en modificado
    }
    return final_html, meta


def main():
    parser = argparse.ArgumentParser(description="Generador A/B headless Fase 4")
    parser.add_argument("--out", required=True, help="Directorio raíz de salida")
    parser.add_argument("--gens", type=int, default=2, help="Generaciones por keyword (default 2)")
    parser.add_argument(
        "--keywords",
        default="",
        help="CSV de subdirs a generar (default: todos). Ej: arq04-review,arq03-educativo",
    )
    parser.add_argument("--no-openai", action="store_true", help="Saltar Stage 2 dual con OpenAI")
    parser.add_argument("--overwrite", action="store_true", help="Sobreescribir HTMLs existentes")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Override de max_tokens del generador (default: core.config.MAX_TOKENS)")
    args = parser.parse_args()

    load_secrets_into_env()

    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        log.error("Falta ANTHROPIC_API_KEY (env o .streamlit/secrets.toml claude_key)")
        sys.exit(1)

    if not args.no_openai and not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY no encontrada → Stage 2 dual será sólo Claude")

    from core.generator import ContentGenerator
    from config.arquetipos import get_arquetipo

    gen_kwargs = {"api_key": api_key}
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
        log.info("Override max_tokens=%d", args.max_tokens)
    generator = ContentGenerator(**gen_kwargs)

    filter_subdirs: Optional[set[str]] = (
        set(s.strip() for s in args.keywords.split(",") if s.strip()) if args.keywords else None
    )

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    failures = []
    total = 0
    metas = []  # telemetría CMS por generación
    for subdir, keyword, arq_code, target_length, _has_reviews in KEYWORDS:
        if filter_subdirs and subdir not in filter_subdirs:
            continue
        arquetipo = get_arquetipo(arq_code)
        if not arquetipo:
            log.error("Arquetipo %s no encontrado, salto %s", arq_code, subdir)
            failures.append((subdir, "missing_arquetipo"))
            continue

        kw_dir = out_root / subdir
        kw_dir.mkdir(parents=True, exist_ok=True)

        for gen_idx in range(1, args.gens + 1):
            out_path = kw_dir / f"gen{gen_idx}.html"
            if out_path.exists() and not args.overwrite:
                log.info("[%s] gen%d ya existe, salto (--overwrite para forzar)", subdir, gen_idx)
                continue

            total += 1
            log.info("[%s] gen%d keyword=%r arq=%s target=%d", subdir, gen_idx, keyword, arq_code, target_length)
            t_start = time.time()
            try:
                html, meta = generate_one(
                    generator=generator,
                    keyword=keyword,
                    arquetipo=arquetipo,
                    target_length=target_length,
                    use_openai=not args.no_openai,
                )
                out_path.write_text(html, encoding="utf-8")
                meta.update({"subdir": subdir, "gen": gen_idx})
                (kw_dir / f"gen{gen_idx}.meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                metas.append(meta)
                log.info("[%s] gen%d OK en %.1fs → %s", subdir, gen_idx, time.time() - t_start, out_path)
            except Exception as e:
                log.exception("[%s] gen%d FAILED: %s", subdir, gen_idx, e)
                failures.append((subdir, f"gen{gen_idx}: {e}"))

    log.info("=== Resumen ===")
    log.info("Generadas: %d", total - len(failures))
    log.info("Falladas: %d", len(failures))
    for sd, err in failures:
        log.info("  - %s: %s", sd, err)

    # --- Telemetría CMS agregada (criterio de éxito Fase 4) ---
    if metas:
        n = len(metas)
        stage3_ok = sum(1 for m in metas if m["stage3_all_present"])
        c_fired = sum(1 for m in metas if m["capa_c_fired"])
        fabricated = sum(1 for m in metas if m["verdict_fabricated"])
        final_ok = sum(1 for m in metas if m["final_all_present"])
        log.info("=== Determinismo CMS ===")
        log.info("Stage 3 con los 3 <article> sin backstop (Capa A): %d/%d (%.0f%%)",
                 stage3_ok, n, 100 * stage3_ok / n)
        log.info("Capa C disparada (backstop necesario): %d/%d (%.0f%%) — objetivo <=20%%",
                 c_fired, n, 100 * c_fired / n)
        log.info("Verdicts fabricados desde cero: %d/%d", fabricated, n)
        log.info("HTML final con los 3 <article> (garantía dura): %d/%d", final_ok, n)
        agg = {
            "n": n, "stage3_all_present": stage3_ok, "capa_c_fired": c_fired,
            "verdict_fabricated": fabricated, "final_all_present": final_ok,
            "per_gen": metas,
        }
        (out_root / "_cms_telemetry.json").write_text(
            json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("Telemetría agregada → %s", out_root / "_cms_telemetry.json")

    sys.exit(0 if not failures else 2)


if __name__ == "__main__":
    main()
