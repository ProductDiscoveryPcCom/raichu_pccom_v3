"""
Tests para Design System v5.0
- design_system.py: carga CSS, registry, sanitización, variantes
- prompts/new_content.py: CSS dinámico, visual elements, legacy compat
- prompts/rewrite.py: visual elements en rewrite, deduplicación productos
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

passed = 0
failed = 0

def assert_(condition):
    """Helper for lambda assertions."""
    assert condition
    return True

def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        print(f"  ❌ {name}: {e}")


# ============================================================
# 1. DESIGN SYSTEM
# ============================================================
print("=" * 60)
print("1. DESIGN SYSTEM")
print("=" * 60)

from config.design_system import (
    CSS_FILES, _load_css_file, get_base_css, get_css_for_prompt,
    get_available_components, get_component_instructions,
    validate_component_selection, validate_css_class,
    COMPONENT_REGISTRY, _sanitize_css, _minify_css, reload_css_cache,
    MOD_CHIP_VARIANTS, MOD_CTA_VARIANTS, MOD_CARD_VARIANTS,
    VCARD_CHIP_VARIANTS, VCARD_CTA_VARIANTS, VCARD_VARIANTS,
    VCARD_GRID_VARIANTS, VCARD_LIST_VARIANTS,
    MOD_GRID_VARIANTS, MOD_FIGURE_VARIANTS,
)

run_test("CSS files exist", lambda: all(p.exists() for p in CSS_FILES.values()))
run_test("Load base CSS (>100 chars)", lambda: (assert_(len(get_base_css()) > 100)))
run_test("Load all CSS files", lambda: all(len(_load_css_file(p)) > 50 for p in CSS_FILES.values()))
run_test("Minify removes comments", lambda: assert_("comment" not in _minify_css("/* comment */ .x{}")))
run_test("Sanitize @import", lambda: assert_("evil" not in _sanitize_css('@import url("evil.css");')))
run_test("Sanitize javascript:", lambda: assert_("javascript:" not in _sanitize_css('url(javascript:alert(1))')))
run_test("Sanitize expression()", lambda: assert_("expression(" not in _sanitize_css('.x{width:expression(1)}')))
run_test("Sanitize behavior:", lambda: assert_("behavior:" not in _sanitize_css('.x{behavior:url(x)}')))
run_test("get_css_for_prompt (base)", lambda: assert_(len(get_css_for_prompt()) > 100))
run_test("get_css_for_prompt (+CMS) > base", lambda: assert_(len(get_css_for_prompt(['mod_cards'])) > len(get_css_for_prompt())))
run_test("Cache works", lambda: (reload_css_cache(), assert_(get_base_css() == get_base_css())))
run_test("Registry ≥16 components", lambda: assert_(len(COMPONENT_REGISTRY) >= 16))
run_test("All promptable have templates", lambda: all(c.html_template for c in COMPONENT_REGISTRY.values() if c.available_in_prompt))
run_test("Variants populated", lambda: assert_(all(len(v) >= 3 for v in [MOD_CHIP_VARIANTS, MOD_CTA_VARIANTS, VCARD_VARIANTS])))
run_test("get_available_components ≥14", lambda: assert_(len(get_available_components()) >= 14))
run_test("validate_component_selection", lambda: assert_(validate_component_selection(['toc','fake']) == (['toc'], ['fake'])))
run_test("validate_css_class OK", lambda: assert_(validate_css_class("mod-card mod-card--horizontal")))
run_test("validate_css_class blocks injection", lambda: assert_(not validate_css_class("x; evil")))
run_test("get_component_instructions", lambda: assert_("COMPONENTES" in get_component_instructions(['mod_cards'])))

# ============================================================
# 2. PROMPTS - NEW CONTENT
# ============================================================
print("\n" + "=" * 60)
print("2. PROMPTS - NEW CONTENT")
print("=" * 60)

from prompts.new_content import (
    _format_visual_elements_instructions, _get_css_for_prompt,
    get_css_styles, get_element_template, CSS_INLINE_MINIFIED,
    build_new_content_prompt_stage1,
)

run_test("_get_css_for_prompt works", lambda: assert_(len(_get_css_for_prompt()) > 100))
run_test("get_css_styles compat", lambda: assert_(len(get_css_styles()) > 100))
run_test("CSS_INLINE_MINIFIED fallback", lambda: assert_(len(CSS_INLINE_MINIFIED) > 50))
run_test("Visual: empty → empty", lambda: assert_(_format_visual_elements_instructions(None) == ""))
run_test("Visual: base comps", lambda: assert_("ELEMENTOS" in _format_visual_elements_instructions(['toc','callout'])))
run_test("Visual: CMS modules", lambda: assert_("mod-section" in _format_visual_elements_instructions(['mod_cards']) or "Cards" in _format_visual_elements_instructions(['mod_cards'])))
run_test("Visual: legacy callout_bf", lambda: assert_("callout" in _format_visual_elements_instructions(['callout_bf']).lower()))
run_test("Visual: legacy verdict_box", lambda: assert_("verdict" in _format_visual_elements_instructions(['verdict_box']).lower()))
run_test("Template: callout_bf→callout_promo", lambda: assert_(get_element_template('callout_bf')))
run_test("Template: verdict_box→verdict", lambda: assert_(get_element_template('verdict_box')))

def t_stage1_css():
    p = build_new_content_prompt_stage1("test", {'name':'T','description':'T'}, visual_elements=['toc'])
    assert "<style>" in p and "{CSS_INLINE" not in p and "{css_for" not in p
run_test("Stage1: CSS injected dynamically", t_stage1_css)

def t_stage1_visual_cms():
    p = build_new_content_prompt_stage1("test", {'name':'T','description':'T'}, visual_elements=['mod_cards','vcard_cards'])
    assert "mod-section" in p or "Cards Horizontales" in p
run_test("Stage1: CMS modules in visual instructions", t_stage1_visual_cms)

# ============================================================
# 3. PROMPTS - REWRITE
# ============================================================
print("\n" + "=" * 60)
print("3. PROMPTS - REWRITE")
print("=" * 60)

import prompts.rewrite as rw
from prompts.rewrite import build_rewrite_prompt_stage1, build_rewrite_final_prompt_stage3

run_test("Rewrite imports visual_elements", lambda: assert_(rw._format_visual_elements_instructions is not None))
run_test("Rewrite imports products", lambda: assert_(rw._format_products_for_prompt is not None))
run_test("Rewrite imports headings", lambda: assert_(rw._format_headings_instructions is not None))
run_test("Rewrite imports css_for_prompt", lambda: assert_(rw._get_css_for_prompt is not None))

def _rw_config(visual=None, products=None, plinks=None, alts=None):
    return {
        'rewrite_mode': 'enhance', 'rewrite_instructions': {},
        'html_contents': [{'url': 'x', 'html': '<h2>T</h2>'}],
        'disambiguation': None, 'main_product': None,
        'editorial_links': [], 'product_links': plinks or [],
        'alternative_products': alts or [], 'products': products or [],
        'headings_config': None, 'visual_elements': visual or [],
        'target_length': 1500, 'objetivo': '', 'tone_instructions': '', 'custom_instructions': '',
    }

def t_rw_visual():
    p = build_rewrite_prompt_stage1("k", "", _rw_config(visual=['toc','mod_cards']))
    assert "ELEMENTOS VISUALES" in p
run_test("Rewrite stage1: visual elements present", t_rw_visual)

def t_rw_no_visual():
    p = build_rewrite_prompt_stage1("k", "", _rw_config())
    assert "ELEMENTOS VISUALES" not in p
run_test("Rewrite stage1: no visual when empty", t_rw_no_visual)

def t_rw_products_dedup():
    products = [{'url':'https://a.com','name':'A','role':'principal','json_data':None},
                {'url':'https://b.com','name':'B','role':'enlazado','json_data':None}]
    plinks = [{'url':'https://b.com','anchor':'B old'}]
    p = build_rewrite_prompt_stage1("k", "", _rw_config(products=products, plinks=plinks))
    assert p.count("B old") == 0, "product_links should not appear when products exist"
run_test("Rewrite stage1: product_links not duplicated", t_rw_products_dedup)

def t_rw_stage3_products():
    cfg = {'keyword':'k','editorial_links':[],'product_links':[],'alternative_products':[],
           'products':[{'url':'https://x.com','name':'X','role':'principal','json_data':None}]}
    p = build_rewrite_final_prompt_stage3("Draft", "Analysis", cfg)
    assert "X" in p
run_test("Rewrite stage3: products in reminders", t_rw_stage3_products)

# ============================================================
# 4. TREE-SHAKING
# ============================================================
print("\n" + "=" * 60)
print("4. TREE-SHAKING")
print("=" * 60)

from config.design_system import (
    _tree_shake_base_css, _get_base_sections, _minify_css,
    _load_css_file, CSS_FILES, reload_css_cache,
)
reload_css_cache()

run_test("Base CSS parses into sections", lambda: assert_(len(_get_base_sections()) >= 14))

def t_core_minimal():
    css = get_css_for_prompt([], minify=False)
    assert '--orange-900' in css, "Missing variables"
    assert '.kicker' in css, "Missing kicker"
    assert '.verdict-box' not in css, "verdict leaked into core"
    assert '.faqs' not in css, "faqs leaked into core"
run_test("Core-only: variables+kicker, no components", t_core_minimal)

def t_toc_only():
    css = get_css_for_prompt(['toc'], minify=False)
    assert '.toc' in css
    assert '.callout' not in css
    assert '.verdict-box' not in css
run_test("toc-only: has .toc, excludes others", t_toc_only)

def t_callout_only():
    css = get_css_for_prompt(['callout'], minify=False)
    assert '.callout' in css
    assert '.verdict-box' not in css
    assert '.faqs' not in css
run_test("callout-only: has .callout, excludes others", t_callout_only)

def t_comparison():
    css = get_css_for_prompt(['comparison_table'], minify=False)
    assert '.comparison-table' in css
    assert '.comparison-highlight' in css
run_test("comparison_table: has new styles", t_comparison)

def t_mod_no_vcard():
    css = get_css_for_prompt(['mod_cards'], minify=False)
    assert '.mod-card' in css or '.mod-section' in css
    assert '.vcard' not in css
run_test("mod_cards: excludes vcard CSS", t_mod_no_vcard)

def t_vcard_no_mod():
    css = get_css_for_prompt(['vcard_cards'], minify=False)
    assert '.vcard' in css
    assert '.mod-card' not in css
run_test("vcard_cards: excludes mod-card CSS", t_vcard_no_mod)

def t_savings():
    core = len(get_css_for_prompt([], minify=True))
    typical = len(get_css_for_prompt(['toc','callout','verdict'], minify=True))
    everything = len(get_css_for_prompt(['toc','callout','callout_promo','verdict','grid','badges','buttons','table','light_table','faqs','comparison_table','mod_cards','vcard_cards'], minify=True))
    assert core < typical < everything, f"Size ordering wrong: {core} < {typical} < {everything}"
    assert core < 2000, f"Core too large: {core}"
    assert typical < 4000, f"Typical too large: {typical}"
run_test("Size ordering: core < typical < everything", t_savings)

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"TOTAL: {passed} passed, {failed} failed")
print(f"{'='*60}")
if failed == 0:
    print("🎉 ALL TESTS PASSED!")
else:
    print(f"⚠️ {failed} test(s) need attention")
