"""A themed replacement for FastAPI's built-in /docs.

Swagger UI ships light-only. This serves the same Swagger UI but wrapped in
Eevie's palette, with a toggle that shares the app's stored preference — so
flipping the theme in the app flips it here too, and the docs don't flashbang
you when you open them from a dark page at night.

The stylesheet only overrides colour, never layout, so a Swagger UI upgrade
can't break the structure — at worst a new element keeps its default colour.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

SWAGGER_CSS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
SWAGGER_JS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"

# Shared with the SPA, so the two stay in step.
THEME_STORAGE_KEY = "ev-platform-theme"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="/favicon.svg">
<link rel="stylesheet" href="{css}">
<style>
  :root {{
    --plane: #f2f6fb;
    --surface: #ffffff;
    --surface-2: #f7f9fd;
    --ink: #0b0b14;
    --ink-2: #4b5169;
    --ink-3: #767c94;
    --edge: rgb(11 11 20 / 0.12);
    --accent: #2563eb;
    --accent-2: #059669;
  }}
  html[data-theme="dark"] {{
    --plane: #08080f;
    --surface: #12131c;
    --surface-2: #171826;
    --ink: #ffffff;
    --ink-2: #a8adc4;
    --ink-3: #6f7590;
    --edge: rgb(255 255 255 / 0.12);
    --accent: #4d8dff;
    --accent-2: #34d399;
  }}

  body {{ margin: 0; background: var(--plane); color: var(--ink); }}
  .swagger-ui .topbar {{ display: none; }}

  /* A small bar of our own, so the toggle has somewhere to live. */
  .eevie-bar {{
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px; border-bottom: 1px solid var(--edge);
    background: var(--surface); position: sticky; top: 0; z-index: 10;
  }}
  .eevie-mark {{
    width: 26px; height: 26px; border-radius: 7px; display: grid; place-items: center;
    background: linear-gradient(135deg, var(--accent-2), var(--accent));
  }}
  .eevie-name {{ font: 600 15px system-ui, sans-serif; color: var(--ink); }}
  .eevie-sub {{ font: 400 13px system-ui, sans-serif; color: var(--ink-3); }}
  .eevie-actions {{ margin-left: auto; display: flex; gap: 8px; }}
  .eevie-btn {{
    display: grid; place-items: center; width: 34px; height: 34px;
    border-radius: 999px; border: 1px solid var(--edge);
    background: var(--surface-2); color: var(--ink-2); cursor: pointer;
  }}
  .eevie-btn:hover {{ color: var(--ink); }}
  .eevie-btn a {{ color: inherit; display: grid; place-items: center; }}

  /* --- dark overrides: colour only ------------------------------------- */
  html[data-theme="dark"] .swagger-ui,
  html[data-theme="dark"] .swagger-ui .info .title,
  html[data-theme="dark"] .swagger-ui .info li,
  html[data-theme="dark"] .swagger-ui .info p,
  html[data-theme="dark"] .swagger-ui .info table,
  html[data-theme="dark"] .swagger-ui label,
  html[data-theme="dark"] .swagger-ui .tab li,
  html[data-theme="dark"] .swagger-ui .opblock-tag,
  html[data-theme="dark"] .swagger-ui .opblock .opblock-summary-operation-id,
  html[data-theme="dark"] .swagger-ui .opblock .opblock-summary-path,
  html[data-theme="dark"] .swagger-ui .opblock .opblock-summary-description,
  html[data-theme="dark"] .swagger-ui .opblock-description-wrapper p,
  html[data-theme="dark"] .swagger-ui .opblock-external-docs-wrapper p,
  html[data-theme="dark"] .swagger-ui .opblock-title_normal p,
  html[data-theme="dark"] .swagger-ui table thead tr td,
  html[data-theme="dark"] .swagger-ui table thead tr th,
  html[data-theme="dark"] .swagger-ui .parameter__name,
  html[data-theme="dark"] .swagger-ui .parameter__type,
  html[data-theme="dark"] .swagger-ui .response-col_status,
  html[data-theme="dark"] .swagger-ui .response-col_links,
  html[data-theme="dark"] .swagger-ui .model-title,
  html[data-theme="dark"] .swagger-ui .model,
  html[data-theme="dark"] .swagger-ui section.models h4,
  html[data-theme="dark"] .swagger-ui .btn {{
    color: var(--ink);
  }}

  html[data-theme="dark"] .swagger-ui .opblock-tag small,
  html[data-theme="dark"] .swagger-ui .parameter__in,
  html[data-theme="dark"] .swagger-ui .prop-format,
  html[data-theme="dark"] .swagger-ui .response-col_description__inner p {{
    color: var(--ink-3);
  }}

  html[data-theme="dark"] .swagger-ui .opblock {{
    background: var(--surface); border-color: var(--edge);
    box-shadow: none;
  }}
  html[data-theme="dark"] .swagger-ui .opblock .opblock-section-header {{
    background: var(--surface-2); box-shadow: none;
  }}
  html[data-theme="dark"] .swagger-ui .opblock-tag {{ border-bottom-color: var(--edge); }}
  html[data-theme="dark"] .swagger-ui section.models,
  html[data-theme="dark"] .swagger-ui section.models .model-container {{
    background: var(--surface); border-color: var(--edge);
  }}
  html[data-theme="dark"] .swagger-ui .scheme-container {{
    background: var(--surface); box-shadow: none; border-bottom: 1px solid var(--edge);
  }}
  html[data-theme="dark"] .swagger-ui input,
  html[data-theme="dark"] .swagger-ui select,
  html[data-theme="dark"] .swagger-ui textarea {{
    background: var(--surface-2); color: var(--ink);
    border-color: var(--edge);
  }}
  html[data-theme="dark"] .swagger-ui .btn {{ border-color: var(--edge); }}
  html[data-theme="dark"] .swagger-ui .responses-inner {{ background: transparent; }}
  html[data-theme="dark"] .swagger-ui table tbody tr td {{ border-color: var(--edge); }}
  html[data-theme="dark"] .swagger-ui .microlight {{
    background: #0c0d15 !important; color: #d8dbe8 !important;
  }}
  /* Swagger draws several icons as black SVG; flip them so they stay visible. */
  html[data-theme="dark"] .swagger-ui svg:not(:root) {{ fill: var(--ink-2); }}
</style>
</head>
<body>
<script>
  // Applied before Swagger renders, so there's no flash of the wrong theme.
  (function () {{
    try {{
      var stored = localStorage.getItem('{storage_key}');
      var dark = stored === 'dark'
        || (stored !== 'light' && !matchMedia('(prefers-color-scheme: light)').matches);
      document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    }} catch (e) {{
      document.documentElement.setAttribute('data-theme', 'dark');
    }}
  }})();
</script>

<div class="eevie-bar">
  <span class="eevie-mark" aria-hidden="true">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#05060c"
         stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M13 2 4 14h7l-1 8 9-12h-7z"/>
    </svg>
  </span>
  <span class="eevie-name">Eevie</span>
  <span class="eevie-sub">API</span>
  <span class="eevie-actions">
    <button class="eevie-btn" id="eevie-theme" type="button" aria-label="Switch theme"></button>
    <span class="eevie-btn"><a href="/" aria-label="Back to the app" title="Back to the app">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>
      </svg>
    </a></span>
  </span>
</div>

<div id="swagger-ui"></div>

<script src="{js}"></script>
<script>
  window.ui = SwaggerUIBundle({{
    url: '{openapi_url}',
    dom_id: '#swagger-ui',
    deepLinking: true,
    // The session cookie must ride along, or every "Execute" comes back 401.
    withCredentials: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: 'BaseLayout',
  }});

  var SUN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  var MOON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  var button = document.getElementById('eevie-theme');
  function paint() {{
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    button.innerHTML = dark ? SUN : MOON;
    button.title = dark ? 'Switch to light' : 'Switch to dark';
  }}
  button.addEventListener('click', function () {{
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    // Same key the app uses, so the choice carries across.
    try {{ localStorage.setItem('{storage_key}', next); }} catch (e) {{}}
    paint();
  }});
  paint();
</script>
</body>
</html>
"""


@router.get("/docs", include_in_schema=False)
def themed_docs() -> HTMLResponse:
    return HTMLResponse(
        PAGE.format(
            title="Eevie API",
            css=SWAGGER_CSS,
            js=SWAGGER_JS,
            openapi_url="/openapi.json",
            storage_key=THEME_STORAGE_KEY,
        )
    )
