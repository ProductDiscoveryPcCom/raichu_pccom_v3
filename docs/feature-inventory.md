# Raichu v5.1.0 — Feature Inventory

Last updated: 2026-04-06

---

## 1. Content Generation Modes

### 1.1 Nuevo (New Content)

| | |
|---|---|
| **What it does** | Generates complete SEO articles from scratch based on keyword + archetype + optional enrichments through a 3-stage pipeline (draft, analysis, final). |
| **Where it lives** | `app.py` → `render_new_content_mode()`, `ui/inputs.py` → `render_content_inputs()`, `core/pipeline.py` → `execute_generation_pipeline(config, mode='new')` |
| **Status** | Working |

### 1.2 Reescritura (Rewrite) — Single

| | |
|---|---|
| **What it does** | Rewrites a single existing article with competitor analysis, maintaining its essence while improving SEO and structure. |
| **Where it lives** | `ui/rewrite.py` → `render_rewrite_section()`, `RewriteMode.SINGLE`, `prompts/rewrite.py` → `build_rewrite_prompt_stage1(config={rewrite_mode:'single'})` |
| **Status** | Working |

### 1.3 Reescritura — Merge (Fusion)

| | |
|---|---|
| **What it does** | Combines 2-5 cannibalized articles into a single authoritative piece, consolidating value from all sources. |
| **Where it lives** | `ui/rewrite.py` → `render_rewrite_section()`, `RewriteMode.MERGE`, `prompts/rewrite.py` → `build_rewrite_prompt_stage1(config={rewrite_mode:'merge'})` |
| **Status** | Working |

### 1.4 Reescritura — Disambiguate

| | |
|---|---|
| **What it does** | Separates hybrid editorial (Post) + transactional (PLP) content into distinct optimized versions to avoid self-cannibalization. |
| **Where it lives** | `ui/rewrite.py` → `render_rewrite_section()`, `RewriteMode.DISAMBIGUATE`, `prompts/rewrite.py` → `build_rewrite_prompt_stage1(config={rewrite_mode:'disambiguate'})` |
| **Status** | Working |

### 1.5 Verificar (Verify Keyword)

| | |
|---|---|
| **What it does** | Checks if a keyword already ranks in GSC to detect cannibalization without generating content (read-only mode). |
| **Where it lives** | `ui/verify.py` → `render_verify_mode()`, `utils/gsc_api.py` → `api_check_cannibalization()`, `utils/gsc_utils.py` → `search_existing_content()` |
| **Status** | Working |

### 1.6 Oportunidades (SEO Opportunities)

| | |
|---|---|
| **What it does** | Identifies high-value SEO opportunities from GSC data: quick wins (pos 11-20), underperformers (low CTR), and declining keywords. |
| **Where it lives** | `ui/opportunities.py` → `render_opportunities_mode()`, `utils/opportunity_scorer.py` → scoring engine, `utils/blog_sitemap.py` → blog URL filtering |
| **Status** | Working |

### 1.7 Asistente (Chat Assistant)

| | |
|---|---|
| **What it does** | Free-form chat interface with internal tool commands (`[GSC_CHECK]`, `[SERP_RESEARCH]`, `[ARQUETIPO_LIST]`, `[GENERAR]`, etc.) that can trigger generation from conversation context. |
| **Where it lives** | `ui/assistant.py`, `app.py` → `_handle_assistant_generation()`, `_build_assistant_guiding_context()` |
| **Status** | Working |

---

## 2. 3-Stage Pipeline

### 2.1 Stage 1 — Draft Generation

| | |
|---|---|
| **What it does** | Claude generates full HTML draft with embedded CSS, archetype structure, product data, and visual elements. |
| **Where it lives** | `core/pipeline.py` → `execute_generation_pipeline()`, `prompts/new_content.py` → `build_new_content_prompt_stage1()`, `prompts/rewrite.py` → `build_rewrite_prompt_stage1()` |
| **Status** | Working |

### 2.2 Stage 2 — Dual Analysis (Claude + OpenAI)

| | |
|---|---|
| **What it does** | Claude analyzes the draft as "senior SEO editor"; OpenAI validates independently; both feedbacks are merged into unified JSON. |
| **Where it lives** | `prompts/new_content.py` → `build_new_content_correction_prompt_stage2()`, `core/openai_client.py` → `generate_dual_analysis()` / `merge_dual_analyses()` |
| **Status** | Working (OpenAI optional — degrades to Claude-only if `openai_key` not in secrets) |

### 2.3 Stage 3 — Final Generation

| | |
|---|---|
| **What it does** | Claude generates the production-ready version incorporating all Stage 2 feedback, enforcing CMS structure (3 articles). |
| **Where it lives** | `prompts/new_content.py` → `build_final_prompt_stage3()`, `prompts/rewrite.py` → `build_rewrite_final_prompt_stage3()` |
| **Status** | Working |

---

## 3. Archetype System

### 3.1 Archetype Registry (34 archetypes)

| | |
|---|---|
| **What it does** | 34 content templates (ARQ-1 to ARQ-34) defining tone, H2/H3 structure, length ranges, visual elements, and guiding questions per content type. |
| **Where it lives** | `config/arquetipos.py` → `ARQUETIPOS` dict |
| **Status** | Working |

**Categories:**
- ARQ-1 to ARQ-5: Fundamentals (articles, guides, reviews, comparatives)
- ARQ-6 to ARQ-10: Lists & selection (buying guides, roundups, price ranges)
- ARQ-11 to ARQ-15: Technical & problem-solving (troubleshooting, specs, setup)
- ARQ-16 to ARQ-20: Trends & events (launches, trends, offers, Black Friday)
- ARQ-21 to ARQ-25: Gaming & entertainment (setups, requirements, streaming, consoles)
- ARQ-26 to ARQ-30: Professional & productivity (workstations, remote work, security)
- ARQ-31 to ARQ-34: Niche (smart home, photography, mobility, sustainability)

### 3.2 Archetype-Specific Guiding Questions

| | |
|---|---|
| **What it does** | Each archetype provides 6-12 contextual questions to elicit user input before generation (e.g., ARQ-4 Review asks for specific product URL). |
| **Where it lives** | `config/arquetipos.py` → `guiding_questions` field per archetype, rendered by `ui/inputs.py` → `render_guiding_questions()` |
| **Status** | Working |

### 3.3 Mini-Stories from Reviews

| | |
|---|---|
| **What it does** | For eligible archetypes, injects real user reviews (advantages, disadvantages, top comments) from product JSON into generated content for authenticity. |
| **Where it lives** | `prompts/new_content.py` → `ARQUETIPOS_CON_MINI_STORIES` (line 57), `_format_product_section()` |
| **Status** | Working (20 archetypes eligible) |

---

## 4. SERP Analysis & Competitor Research

### 4.1 SERP Research (Stage 0)

| | |
|---|---|
| **What it does** | Analyzes top 10 Google.es results before generation: scrapes competitor content, collects word counts, heading patterns, search intent, and related searches. |
| **Where it lives** | `utils/serp_research.py` → `research_serp()`, `_scrape_competitors()`, `_analyze_structure()` |
| **Status** | Working (SerpAPI primary, DuckDuckGo fallback) |

### 4.2 Competitor Scraping

| | |
|---|---|
| **What it does** | Scrapes competitor pages to extract content structure (headings, word count, tables, FAQs, pricing), product info, and meta tags. |
| **Where it lives** | `core/scraper.py` → `scrape_competitor_urls()`, `scrape_url()`, `extract_product_info()`, `extract_page_content()` |
| **Status** | Working (0.5s delays between requests, 10MB max response) |

### 4.3 SEMrush Keyword Research

| | |
|---|---|
| **What it does** | Fetches keyword difficulty, volume, CPC, and related keywords from SEMrush API with rate limiting and caching. |
| **Where it lives** | `core/semrush.py` → singleton client with `rate_limit=10 req/sec`, `cache_ttl=1hr` |
| **Status** | Working (requires `semrush.api_key` in secrets; supports ES/US/UK/FR/DE/IT/BR/MX databases) |

---

## 5. Visual Elements & Design System

### 5.1 Component Registry

| | |
|---|---|
| **What it does** | 20+ CSS components (TOC, callout, table, light_table, grid, verdict, badges, cards, comparison_table, etc.) with variant support and HTML templates. |
| **Where it lives** | `config/design_system.py` → component registry, `get_available_components()`, `get_component_instructions()` |
| **Status** | Working |

### 5.2 CSS Tree-Shaking

| | |
|---|---|
| **What it does** | Only includes CSS for selected components in prompts, reducing token usage; always includes core variables/reset/typography. |
| **Where it lives** | `config/design_system.py` → `get_css_for_prompt(selected_components, minify)` |
| **Status** | Working |

### 5.3 Horizontal Cards Module (mod_cards)

| | |
|---|---|
| **What it does** | CMS-compatible horizontal card system with image support: 5 card variants, 4 chip/CTA/grid variants each. |
| **Where it lives** | `config/design_system.py` → `mod_cards` component, CSS from `cards_con_imagenes.css` |
| **Status** | Working |

### 5.4 Vertical Cards Module (vcard_cards)

| | |
|---|---|
| **What it does** | CMS-compatible vertical recommendation cards: 4 main variants, 7 chip variants, 5 CTA variants. |
| **Where it lives** | `config/design_system.py` → `vcard_cards` component, CSS from `cards_recomendacion.css` |
| **Status** | Working |

### 5.5 Visual Elements Validation (Stage 2)

| | |
|---|---|
| **What it does** | Verifies all selected visual components are present in the generated HTML during Stage 2 analysis. |
| **Where it lives** | `prompts/new_content.py` → `_build_visual_elements_minimum_check()` |
| **Status** | Working |

---

## 6. Briefing System (Guiding Context)

### 6.1 Archetype-Specific Briefing

| | |
|---|---|
| **What it does** | Q&A form with archetype-specific questions (top 3 shown, rest behind toggle) plus 4 universal questions; answers formatted and injected into Stage 1 prompt. |
| **Where it lives** | `ui/inputs.py` → `render_guiding_questions()` (line 1084) |
| **Status** | Working (available in New and Rewrite modes) |

### 6.2 Assistant Guiding Context

| | |
|---|---|
| **What it does** | Builds generation context from last 3-4 chat messages + tool results (SERP, GSC, product analysis) when launching generation from Assistant mode. |
| **Where it lives** | `app.py` → `_build_assistant_guiding_context()` (line 577) |
| **Status** | Working |

---

## 7. Linking System (Internal / External)

### 7.1 Internal Editorial Links

| | |
|---|---|
| **What it does** | Up to 10 internal links to PcComponentes posts/categories with custom anchor text; passed through all 3 pipeline stages. |
| **Where it lives** | `ui/inputs.py` → `render_links_with_anchors(link_type='internal')` |
| **Status** | Working |

### 7.2 PDP Product Links

| | |
|---|---|
| **What it does** | Product page links with anchor text + optional JSON product data per link; enriches generated content with product context. |
| **Where it lives** | `ui/inputs.py` → `render_links_with_anchors(link_type='pdp')` |
| **Status** | Working |

### 7.3 Link Verification (Stage 2)

| | |
|---|---|
| **What it does** | Stage 2 analysis checks that all provided links appear in the generated HTML; flags missing links as issues. |
| **Where it lives** | `prompts/new_content.py` → `build_new_content_correction_prompt_stage2()` parameter `links_to_verify` |
| **Status** | Working |

---

## 8. Quality Checks

### 8.1 Anti-AI Phrase Detection

| | |
|---|---|
| **What it does** | Detects and flags 71 Spanish AI-typical phrases ("En el mundo actual...", "Sin lugar a dudas...", empty adjectives, etc.) in generated content. |
| **Where it lives** | `prompts/brand_tone.py` → `INSTRUCCIONES_ANTI_IA`, `ANTI_IA_CHECKLIST_STAGE2`; `utils/quality_scorer.py` → Humanidad/Voz dimension |
| **Status** | Working |

### 8.2 Content Quality Scoring (5 dimensions)

| | |
|---|---|
| **What it does** | Multi-dimensional quality evaluation: Humanidad/Voz (30%), Especificidad (25%), Balance estructural (20%), SEO (15%), Legibilidad (10%). Pass threshold: 70/100. |
| **Where it lives** | `utils/quality_scorer.py` |
| **Status** | Working |

### 8.3 Keyword Analysis

| | |
|---|---|
| **What it does** | Measures keyword density (target 1-2%), placement (H2, first 100 words, last 150 words), and stuffing risk. |
| **Where it lives** | `utils/keyword_analyzer.py` → `KeywordAnalyzer.analyze()` |
| **Status** | Working |

### 8.4 CSS Integrity Validation

| | |
|---|---|
| **What it does** | Verifies CSS consistency across 3 sources: design_system.py, cms_compatible.css, and prompts/new_content.py fallback CSS. |
| **Where it lives** | `utils/css_integrity.py` |
| **Status** | Working |

### 8.5 Table Fixer

| | |
|---|---|
| **What it does** | Auto-corrects structural issues in Claude-generated tables: adds `<thead>/<tbody>`, wraps responsive tables, validates column consistency. |
| **Where it lives** | `utils/table_fixer.py` |
| **Status** | Working (idempotent) |

### 8.6 Content Scrubber

| | |
|---|---|
| **What it does** | Removes 11 types of Unicode watermarks/invisible characters and normalizes em-dashes to Spanish punctuation. |
| **Where it lives** | `utils/content_scrubber.py` |
| **Status** | Working (idempotent) |

### 8.7 Archetype-Specific Validation (QW-1)

| | |
|---|---|
| **What it does** | Generates a checklist of structure requirements specific to each archetype (e.g., ARQ-4 must have comparison table, FAQs, final verdict). |
| **Where it lives** | `prompts/new_content.py` → `_build_archetype_checklist_stage2()` |
| **Status** | Working |

---

## 9. Export & Download Options

### 9.1 HTML Download

| | |
|---|---|
| **What it does** | Downloads the final generated HTML as a file named `{keyword_slug}_{date}.html`. |
| **Where it lives** | `ui/results.py` → `render_content_tab()` (line 230), `st.download_button()` |
| **Status** | Working |

### 9.2 Copy to Clipboard

| | |
|---|---|
| **What it does** | Copies final HTML to clipboard via JavaScript `navigator.clipboard.writeText()`. |
| **Where it lives** | `ui/results.py` → `render_copy_button()` (line 1730) |
| **Status** | Working |

### 9.3 Export All Stages (ZIP)

| | |
|---|---|
| **What it does** | Exports Draft (Stage 1) + Analysis (Stage 2) + Final (Stage 3) as a single ZIP file. |
| **Where it lives** | `ui/results.py` → `render_export_all_button()` (line 1808) |
| **Status** | Working |

### 9.4 Image Downloads

| | |
|---|---|
| **What it does** | Download individual generated images in original format, format variants (JPEG, WebP, PNG), or all as ZIP. |
| **Where it lives** | `ui/results.py` (lines 2181-2209) |
| **Status** | Working |

### 9.5 Translation Download

| | |
|---|---|
| **What it does** | Download translated HTML per language as `content_{lang_code}_{timestamp}.html`. |
| **Where it lives** | `ui/results.py` (line 1190) |
| **Status** | Working |

---

## 10. CMS Integration

### 10.1 CMS Publishing (Draft)

| | |
|---|---|
| **What it does** | Publishes generated HTML as draft to WordPress (with Yoast SEO metadata) or custom REST API endpoints. |
| **Where it lives** | `core/cms_publisher.py` → `publish_draft()`, `_publish_wordpress()`, `_publish_custom()` |
| **Status** | Working (auth: Basic for WP, Bearer for custom) |

### 10.2 CMS-Required HTML Structure

| | |
|---|---|
| **What it does** | Enforces 3-article structure required by PcComponentes CMS: `contentGenerator__main`, `contentGenerator__faqs`, `contentGenerator__verdict`. |
| **Where it lives** | Enforced in all prompt functions (Stage 1/2/3) across `prompts/new_content.py` and `prompts/rewrite.py` |
| **Status** | Working |

---

## 11. External API Integrations

### 11.1 Anthropic (Claude)

| | |
|---|---|
| **What it does** | Primary AI engine for all 3 pipeline stages; model `claude-sonnet-4-20250514`. |
| **Where it lives** | `core/generator.py` → `ContentGenerator`, `core/config.py` → bridge pattern |
| **Status** | Working |

### 11.2 OpenAI (GPT-4.1)

| | |
|---|---|
| **What it does** | Secondary AI for Stage 2 dual correction; model `gpt-4.1-2025-04-14`. |
| **Where it lives** | `core/openai_client.py` → `call_openai_api()`, `generate_dual_analysis()`, `merge_dual_analyses()` |
| **Status** | Working (optional — graceful degradation if key missing) |

### 11.3 Google Gemini 2.5 Flash

| | |
|---|---|
| **What it does** | Generates contextual images in 5 types (cover, body contextual, body use case, infographic, summary) with multiple format outputs. |
| **Where it lives** | `utils/image_gen.py` → `ImageRequest`, `GeneratedImage`, `ImageGenResult` |
| **Status** | Working (images exported separately, not embedded in HTML) |

### 11.4 Google Search Console API

| | |
|---|---|
| **What it does** | Real-time cannibalization detection via Service Account auth; 180-day query window, 50-impression minimum, intelligent stopword-filtered matching. |
| **Where it lives** | `utils/gsc_api.py` → `api_check_cannibalization()`, `api_search_existing_content()`, `is_gsc_api_configured()` |
| **Status** | Working (CSV fallback via `utils/gsc_utils.py` if API unconfigured) |

### 11.5 SEMrush API

| | |
|---|---|
| **What it does** | Keyword research, domain overview, and difficulty analysis with rate limiting (10 req/sec), caching (1hr TTL), and multi-region support. |
| **Where it lives** | `core/semrush.py` → thread-safe singleton client |
| **Status** | Working (requires `semrush.api_key` in secrets) |

### 11.6 SerpAPI

| | |
|---|---|
| **What it does** | Structured SERP results for competitive intelligence (primary source for SERP research). |
| **Where it lives** | `utils/serp_research.py` → `research_serp()`, `_get_serpapi_key()` |
| **Status** | Working (DuckDuckGo fallback if unconfigured) |

### 11.7 n8n Webhooks

| | |
|---|---|
| **What it does** | Fetches product data from PcComponentes via n8n workflows; parses flexible response formats (lists/dicts, multiple field mappings). |
| **Where it lives** | `core/n8n_integration.py` → `fetch_product_via_n8n_webhook()`, `get_product_data()` |
| **Status** | Working (webhook URL from `st.secrets['n8n']['webhook_url']`) |

---

## 12. Additional Features

### 12.1 Translation (6 languages)

| | |
|---|---|
| **What it does** | Context-aware translation (not literal) to ES, EN, FR, PT, DE, IT with per-country localization (currency, vocabulary, tone). |
| **Where it lives** | `utils/translation.py` → `LanguageConfig` dataclass per language |
| **Status** | Working |

### 12.2 Brand Tone System

| | |
|---|---|
| **What it does** | Enforces PcComponentes brand personality across all generated content: expert but accessible, geeky, honest, warm. Includes positive orientation rules (never leave user without a purchase path). |
| **Where it lives** | `prompts/brand_tone.py` → `get_tone_instructions()`, `get_system_prompt_base()`, `PERSONALIDAD_MARCA`, `INSTRUCCIONES_ORIENTACION_POSITIVA` |
| **Status** | Working |

### 12.3 Secondary Keywords

| | |
|---|---|
| **What it does** | Accepts up to 15 LSI/semantic keywords (one per line) to improve content coverage; passed alongside primary keyword. |
| **Where it lives** | `ui/inputs.py` → secondary keywords textarea |
| **Status** | Working |

### 12.4 Headings Configuration

| | |
|---|---|
| **What it does** | Manual override of heading distribution (H2: 1-15, H3: 0-30, H4: 0-20) for fine-grained article structure control. |
| **Where it lives** | `ui/inputs.py` → `render_headings_config()` |
| **Status** | Working |

### 12.5 Alternative Product

| | |
|---|---|
| **What it does** | Specifies a fallback product to recommend when the main product doesn't fit the user's needs; includes URL, name, and JSON data. |
| **Where it lives** | `ui/inputs.py` → `render_alternative_product_input()` |
| **Status** | Working |

### 12.6 Multi-Product Support (v5.0)

| | |
|---|---|
| **What it does** | Unified product list with roles (principal, alternativo, enlazado) and individual JSON data per product. |
| **Where it lives** | `ui/inputs.py` → `render_products_section()`, `prompts/new_content.py` → `_format_products_for_prompt()` |
| **Status** | Working |

### 12.7 YouTube Embed

| | |
|---|---|
| **What it does** | Extracts YouTube video IDs from 5+ URL formats and generates responsive CMS-compatible embeds. |
| **Where it lives** | `utils/youtube_embed.py` → `extract_video_id()`, `generate_responsive_embed()` |
| **Status** | Working |

### 12.8 Meta & TLDR Generation

| | |
|---|---|
| **What it does** | Generates SEO metadata in a single Claude call: meta title (<=60 chars), meta description (<=155 chars), TL;DR title (<=80 chars), TL;DR description (<=200 chars). |
| **Where it lives** | `utils/meta_generator.py` |
| **Status** | Working |

### 12.9 Opportunity Scoring

| | |
|---|---|
| **What it does** | Multi-factor scoring for SEO opportunities: impressions (25%), position (20%), commercial intent (20%), difficulty (15%), CTR gap (10%), trend (10%). Classifies as QUICK_WIN, IMPROVEMENT, NEW_CONTENT, DECLINING, or UNDERPERFORMER. |
| **Where it lives** | `utils/opportunity_scorer.py` |
| **Status** | Working |

### 12.10 Session State Isolation

| | |
|---|---|
| **What it does** | Saves/restores generation results per mode when switching, preventing loss of in-progress work. |
| **Where it lives** | `core/session.py` → `_save_mode_results()`, `_restore_mode_results()` |
| **Status** | Working |

### 12.11 Authentication

| | |
|---|---|
| **What it does** | HMAC-based password authentication via `st.secrets`; allows free access if no password configured. |
| **Where it lives** | `core/auth.py` |
| **Status** | Working |

### 12.12 Graceful Degradation

| | |
|---|---|
| **What it does** | Every UI module is imported with try/except and `_X_available` flag; if a module fails, the app continues without that feature. |
| **Where it lives** | `app.py` → all import blocks |
| **Status** | Working |

### 12.13 Blog Sitemap Parser

| | |
|---|---|
| **What it does** | Parses PcComponentes blog XML sitemap to detect published posts; 1-hour TTL cache. Used in Opportunities mode to filter blog-only URLs. |
| **Where it lives** | `utils/blog_sitemap.py` |
| **Status** | Working |
