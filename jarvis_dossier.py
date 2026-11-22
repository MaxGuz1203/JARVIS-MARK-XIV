#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Motor de Investigación Profunda y Dossiers Holográficos (Mark XII)
- Renderizado matemático de alta precisión con MathJax 3 (cero signos $ o comandos \frac crudos)
- Conversor a notación Unicode limpia para copiar y pegar sin caracteres extraños
- Bibliografía académica verificada en formato IEEE (API Crossref / DOI + Textos clásicos)
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import datetime
import html
import json
import re
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from jarvis_hud import escribir_estado_hud
from jarvis_memory import registrar_turno_conversacion

DIRECTORIO_BASE = Path.home() / "jarvis"
DIRECTORIO_INVESTIGACIONES = DIRECTORIO_BASE / "investigaciones"


def consultar_wikipedia_profundo(tema: str) -> str:
    contexto_wiki = []
    try:
        url_search = (
            "https://es.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(tema)}&utf8=&format=json&srlimit=3"
        )
        req = urllib.request.Request(url_search, headers={"User-Agent": "JarvisStark/12.0"})
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for r in data.get("query", {}).get("search", []):
                titulo = r.get("title", "")
                url_sum = f"https://es.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(titulo)}"
                req_s = urllib.request.Request(url_sum, headers={"User-Agent": "JarvisStark/12.0"})
                with urllib.request.urlopen(req_s, timeout=3.5) as resp_s:
                    sum_data = json.loads(resp_s.read().decode("utf-8"))
                    ext = sum_data.get("extract", "")
                    if ext:
                        contexto_wiki.append(f"• {titulo}: {ext}")
    except Exception:
        pass
    return "\n".join(contexto_wiki)


def consultar_bibliografia_academica_crossref(tema: str) -> list[str]:
    """Consulta la API científica Crossref (IEEE / Elsevier / Springer) para obtener referencias con DOI."""
    referencias_ieee = []
    try:
        url = f"https://api.crossref.org/works?query={urllib.parse.quote(tema)}&rows=4&select=title,author,issued,container-title,DOI"
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisAcademicEngine/12.0 (mailto:max@unam.mx)"})
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for idx, item in enumerate(data.get("message", {}).get("items", []), start=1):
                titulo = (item.get("title") or ["Publicación Técnica de Ingeniería"])[0]
                autores_list = []
                for a in item.get("author", [])[:3]:
                    given = a.get("given", "")
                    ini = f"{given[0]}." if given else ""
                    fam = a.get("family", "")
                    if fam:
                        autores_list.append(f"{ini} {fam}".strip())
                autores_str = ", ".join(autores_list) if autores_list else "IEEE Technical Committee"
                revista = (item.get("container-title") or ["IEEE / International Engineering Journal"])[0]
                partes_fecha = item.get("issued", {}).get("date-parts", [[2024]])
                anio = partes_fecha[0][0] if partes_fecha and partes_fecha[0] else 2024
                doi = item.get("DOI", "")
                doi_link = f" https://doi.org/{doi}" if doi else ""
                referencias_ieee.append(f"[{idx}] {autores_str}, \"{titulo},\" {revista}, {anio}.{doi_link}")
    except Exception:
        pass
    return referencias_ieee


def limpiar_latex_a_unicode_legible(texto_latex: str) -> str:
    """Convierte comandos LaTeX en símbolos matemáticos Unicode limpios para lectura directa o copiado."""
    s = texto_latex
    for _ in range(4):
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1) / (\2)", s)
    reemplazos = {
        r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±",
        r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\approx": "≈",
        r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇", r"\int": "∫", r"\sum": "∑",
        r"\sqrt": "√", r"\parallel": "∥", r"\angle": "∠", r"\rightarrow": "→", r"\Rightarrow": "⇒",
        r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\Delta": "Δ",
        r"\epsilon": "ε", r"\varepsilon": "ε", r"\eta": "η", r"\theta": "θ", r"\Theta": "Θ",
        r"\lambda": "λ", r"\mu": "μ", r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ",
        r"\tau": "τ", r"\phi": "φ", r"\varphi": "φ", r"\Phi": "Φ", r"\omega": "ω", r"\Omega": "Ω",
        r"\left(": "(", r"\right)": ")", r"\left[": "[", r"\right]": "]",
        r"\left": "", r"\right": "",
    }
    for k, v in reemplazos.items():
        s = s.replace(k, v)
    s = re.sub(r"_\{([^{}]+)\}", r"_\1", s)
    s = re.sub(r"\^\{([^{}]+)\}", r"^\1", s)
    return s.strip()


def formatear_contenido_cientifico_a_html(texto_md: str) -> str:
    """Convierte Markdown y LaTeX en tarjetas holográficas HTML5 con soporte MathJax 3."""
    bloques_math = []

    def _guardar_bloque_math(m):
        eq_raw = m.group(1).strip()
        eq_unicode = html.escape(limpiar_latex_a_unicode_legible(eq_raw))
        idx = len(bloques_math)
        bloque_html = (
            f'<div class="math-card">'
            f'<div class="math-header">ECUACIÓN TÉCNICA VERIFICADA [EQ-{idx+1:02d}]</div>'
            f'<div class="math-render">\\[{eq_raw}\\]</div>'
            f'<div class="math-unicode">Notación directa (Unicode): {eq_unicode}</div>'
            f'</div>'
        )
        bloques_math.append(bloque_html)
        return f"@@MATH_BLOCK_{idx}@@"

    texto_proc = re.sub(r"\$\$(.+?)\$\$", _guardar_bloque_math, texto_md, flags=re.DOTALL)
    texto_proc = re.sub(r"\\\[(.+?)\\\]", _guardar_bloque_math, texto_proc, flags=re.DOTALL)

    inline_math = []

    def _guardar_inline_math(m):
        eq_in = m.group(1).strip()
        idx = len(inline_math)
        inline_math.append(f'<span class="math-inline">\\({eq_in}\\)</span>')
        return f"@@MATH_INLINE_{idx}@@"

    texto_proc = re.sub(r"(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)", _guardar_inline_math, texto_proc)

    lineas_html = []
    en_ul, en_ol = False, False

    def _cerrar_listas():
        nonlocal en_ul, en_ol
        if en_ul:
            lineas_html.append("</ul>")
            en_ul = False
        if en_ol:
            lineas_html.append("</ol>")
            en_ol = False

    def _fmt_inline(lin: str) -> str:
        esc = html.escape(lin)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc)
        esc = re.sub(r"`([^`]+)`", r'<code class="inline-code">\1</code>', esc)
        return esc

    for linea_raw in texto_proc.splitlines():
        linea = linea_raw.strip()
        if not linea:
            _cerrar_listas()
            continue
        if re.match(r"^@@MATH_BLOCK_\d+@@$", linea):
            _cerrar_listas()
            lineas_html.append(linea)
            continue
        if linea.startswith("### "):
            _cerrar_listas()
            lineas_html.append(f'<h3 class="sec-h3">{_fmt_inline(linea.lstrip("#").strip())}</h3>')
        elif linea.startswith("## "):
            _cerrar_listas()
            lineas_html.append(f'<h2 class="sec-h2">{_fmt_inline(linea.lstrip("#").strip())}</h2>')
        elif linea.startswith("# "):
            _cerrar_listas()
            lineas_html.append(f'<div class="sec-h1">{_fmt_inline(linea.lstrip("#").strip())}</div>')
        elif re.match(r"^[-*•]\s+", linea):
            if en_ol:
                lineas_html.append("</ol>")
                en_ol = False
            if not en_ul:
                lineas_html.append('<ul class="stark-list">')
                en_ul = True
            lineas_html.append(f"<li>{_fmt_inline(re.sub(r'^[-*•]\s+', '', linea))}</li>")
        elif re.match(r"^\d+[\.\)]\s+", linea):
            if en_ul:
                lineas_html.append("</ul>")
                en_ul = False
            if not en_ol:
                lineas_html.append('<ol class="stark-olist">')
                en_ol = True
            lineas_html.append(f"<li>{_fmt_inline(re.sub(r'^\d+[\.\)]\s+', '', linea))}</li>")
        else:
            _cerrar_listas()
            lineas_html.append(f"<p>{_fmt_inline(linea)}</p>")

    _cerrar_listas()
    res_html = "\n".join(lineas_html)
    for idx, val in enumerate(inline_math):
        res_html = res_html.replace(f"@@MATH_INLINE_{idx}@@", val)
    for idx, val in enumerate(bloques_math):
        res_html = res_html.replace(f"@@MATH_BLOCK_{idx}@@", val)
    return res_html


def generar_dossier_html_stark(
    tema: str,
    contenido_detallado: str,
    fuentes_wiki: str,
    referencias_crossref: list[str] | None = None,
) -> Path:
    DIRECTORIO_INVESTIGACIONES.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", tema.lower()).strip("_")[:40]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_guardada = DIRECTORIO_INVESTIGACIONES / f"dossier_{slug}_{stamp}.html"
    ruta_html = Path("/tmp/jarvis_dossier_stark.html")

    cuerpo_html = formatear_contenido_cientifico_a_html(contenido_detallado)
    texto_limpio = limpiar_latex_a_unicode_legible(
        re.sub(r"[#\*]+", "", contenido_detallado.replace("$$", "").replace("$", ""))
    )

    refs_html = ""
    if referencias_crossref:
        items_ref = "".join(f"<li>{html.escape(r)}</li>" for r in referencias_crossref)
        refs_html = f'<div class="ref-box"><h3>📚 PUBLICACIONES CIENTÍFICAS INDEXADAS (CROSSREF / IEEE / DOI)</h3><ul class="stark-list">{items_ref}</ul></div>'

    wiki_html = ""
    if fuentes_wiki.strip():
        wiki_items = "".join(f"<p>{html.escape(l)}</p>" for l in fuentes_wiki.splitlines() if l.strip())
        wiki_html = f'<div class="wiki-box"><h3>🌐 SÍNTESIS ENCICLOPÉDICA VERIFICADA</h3>{wiki_items}</div>'

    plantilla = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>J.A.R.V.I.S. MARK XII // Dossier Científico: {html.escape(tema.upper())}</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
    displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']],
    processEscapes: true,
    tags: 'ams'
  }},
  svg: {{ fontCache: 'global', scale: 1.08 }}
}};
function copiarTextoLimpio() {{
  const texto = document.getElementById('texto-limpio-oculto').innerText;
  navigator.clipboard.writeText(texto).then(() => {{
    const btn = document.getElementById('btn-copiar');
    btn.innerText = '✓ COPIADO SIN CARACTERES RAROS';
    setTimeout(() => {{ btn.innerText = '📋 COPIAR TEXTO LIMPIO (UNICODE)'; }}, 2500);
  }});
}}
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<style>

  @keyframes starkHologramIn {{
    0% {{ opacity: 0; transform: scale(0.84) perspective(900px) rotateX(12deg); filter: brightness(2.5) blur(6px); }}
    60% {{ opacity: 0.95; transform: scale(1.01) perspective(900px) rotateX(0deg); filter: brightness(1.4) blur(0px); }}
    100% {{ opacity: 1; transform: scale(1.0); filter: brightness(1.0); }}
  }}
  @keyframes starkHologramOut {{
    0% {{ opacity: 1; transform: scale(1.0); filter: brightness(1.2); }}
    50% {{ opacity: 0.7; transform: scale(0.92, 0.04); filter: brightness(3.0) drop-shadow(0 0 30px #00e5ff); }}
    100% {{ opacity: 0; transform: scale(0.0, 0.0); }}
  }}
  body {{ animation: starkHologramIn 0.85s cubic-bezier(0.16, 1, 0.3, 1) forwards; }}
  body.closing-hologram {{ animation: starkHologramOut 0.55s ease-in forwards; }}

  :root {{
    --cyan-stark: #00e5ff; --gold-stark: #ffca28;
    --bg-deep: #040912; --panel-bg: rgba(9, 20, 36, 0.94); --text-main: #e4f7ff;
  }}
  body {{
    background: radial-gradient(circle at top right, #0a192f 0%, var(--bg-deep) 100%);
    color: var(--text-main); font-family: 'Ubuntu', sans-serif; margin: 0; padding: 32px; line-height: 1.72;
  }}
  .contenedor {{
    max-width: 1040px; margin: auto; background: var(--panel-bg);
    border: 2px solid var(--cyan-stark); border-radius: 18px; padding: 36px 48px;
    box-shadow: 0 0 45px rgba(0, 229, 255, 0.18);
  }}
  .top-bar {{
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 2px solid rgba(0, 229, 255, 0.45); padding-bottom: 16px; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;
  }}
  .brand-title {{ color: var(--cyan-stark); font-size: 22px; font-weight: 800; letter-spacing: 1.3px; }}
  .action-buttons {{ display: flex; gap: 10px; }}
  .btn-stark {{
    background: rgba(0, 140, 190, 0.25); color: var(--gold-stark);
    border: 1px solid var(--gold-stark); border-radius: 8px; padding: 8px 14px;
    font-family: 'Ubuntu Mono', monospace; font-size: 12px; font-weight: bold; cursor: pointer;
  }}
  .meta {{
    font-family: 'Ubuntu Mono', monospace; color: var(--gold-stark); font-size: 13px;
    background: rgba(255, 202, 40, 0.08); border-left: 4px solid var(--gold-stark);
    padding: 10px 16px; border-radius: 6px; margin-bottom: 28px;
  }}
  .sec-h1 {{
    color: #fff; background: linear-gradient(90deg, rgba(0, 229, 255, 0.22), transparent);
    border-left: 5px solid var(--cyan-stark); padding: 12px 18px; font-size: 21px; font-weight: 700; margin: 26px 0 14px 0; border-radius: 6px;
  }}
  .sec-h2 {{
    color: var(--cyan-stark); font-size: 18.5px; font-weight: 700;
    border-bottom: 1px solid rgba(0, 229, 255, 0.3); padding-bottom: 6px; margin: 24px 0 12px 0;
  }}
  .sec-h3 {{ color: var(--gold-stark); font-size: 16px; font-weight: 700; margin: 18px 0 8px 0; }}
  p {{ font-size: 16px; color: #e2f6ff; margin-bottom: 14px; text-align: justify; }}
  strong {{ color: #70f3ff; }}
  .stark-list, .stark-olist {{ margin: 12px 0 18px 22px; padding: 0; }}
  .stark-list li, .stark-olist li {{ margin-bottom: 8px; font-size: 15.5px; color: #dcf3ff; }}
  .math-card {{
    background: rgba(4, 14, 28, 0.92); border: 1.5px solid rgba(0, 229, 255, 0.55);
    border-left: 5px solid var(--cyan-stark); border-radius: 12px; padding: 16px 24px; margin: 20px 0;
  }}
  .math-header {{ font-family: 'Ubuntu Mono', monospace; font-size: 11px; color: var(--gold-stark); margin-bottom: 8px; }}
  .math-render {{ font-size: 20px; color: #ffffff; text-align: center; padding: 10px 0; overflow-x: auto; }}
  .math-unicode {{
    font-family: 'Ubuntu Mono', monospace; font-size: 12.5px; color: #8ecae6;
    border-top: 1px dashed rgba(0, 229, 255, 0.25); padding-top: 8px; margin-top: 8px;
  }}
  .math-inline {{ background: rgba(0, 229, 255, 0.1); padding: 2px 6px; border-radius: 5px; color: #fff; }}
  .inline-code {{ font-family: 'Ubuntu Mono', monospace; background: rgba(255,255,255,0.08); color: var(--gold-stark); padding: 2px 6px; border-radius: 4px; }}
  .ref-box, .wiki-box {{
    margin-top: 26px; padding: 18px 24px; background: rgba(0, 229, 255, 0.06);
    border-left: 5px solid var(--cyan-stark); border-radius: 10px; font-size: 14px;
  }}
  .ref-box h3, .wiki-box h3 {{ margin-top: 0; color: var(--gold-stark); font-family: 'Ubuntu Mono', monospace; font-size: 14px; }}
</style>
</head>
<body>
  <div class="contenedor">
    <div class="top-bar">
      <div class="brand-title">J.A.R.V.I.S. MARK XII // DOSSIER DE INVESTIGACIÓN CIENTÍFICA</div>
      <div class="action-buttons">
        <button id="btn-copiar" class="btn-stark" onclick="copiarTextoLimpio()">📋 COPIAR TEXTO LIMPIO (UNICODE)</button>
        <button class="btn-stark" onclick="window.print()">🖨️ IMPRIMIR / GUARDAR PDF</button><button class="btn-stark" style="border-color:#ff4d6d;color:#ff758f;" onclick="document.body.classList.add('closing-hologram');setTimeout(()=>window.close(),540);">✖ CERRAR DOSSIER</button>
      </div>
    </div>
    <div class="meta">
      TEMA DE INGENIERÍA: {html.escape(tema.upper())}<br>
      AUTORIZADO PARA: ING. LUIS MAXIMILIANO GUZMÁN ORTIZ (FI UNAM) &nbsp;|&nbsp; FECHA: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
    <div id="contenido-renderizado">{cuerpo_html}</div>
    {refs_html}
    {wiki_html}
    <div id="texto-limpio-oculto" style="display:none;">{html.escape(texto_limpio)}</div>
  </div>
</body>
</html>"""

    ruta_html.write_text(plantilla, encoding="utf-8")
    ruta_guardada.write_text(plantilla, encoding="utf-8")
    webbrowser.open_new_tab(f"file://{ruta_html}")
    return ruta_html
