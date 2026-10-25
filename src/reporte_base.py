# Copiado de _profeco_core/src/reporte_base.py por publicar.py; no editar aquí.
"""Plantilla del reporte HTML autocontenido (Plotly embebido), con el diseño de mexico-mismo-producto-precio.

Uso en un análisis:
    import reporte_base as RB
    fig = go.Figure(...); fig.update_layout(**RB.layout(height=640, title=RB.title("Hallazgo", "Qué se mide")))
    html = RB.page(
        titulo="Mismo producto, distinto precio",
        descripcion="Una frase para buscadores.",
        objetivo="Qué decisión ayuda a tomar y para quién.",
        h1="Hallazgo principal con <span class='pos'>cifra</span>",
        intro="Qué se compara, dónde y cuándo.",
        stats=[("▲ +19%", "pos", "texto"), ...],
        secciones=[("Título con <b>énfasis</b>", "Párrafo", "<div class='card'>…</div>"), ...],
        acciones=[("Equipo comercial", "acción concreta"), ...],
        galeria=[("Título", "Pie", ruta_png), ...],
        metodo=["…", "…"],
    )
    RB.write(html, ROOT / "docs/index.html")

La página abre con el objetivo, cierra con método y límites, y lleva la fuente y la firma en el pie.
Colores por signo: clase `pos` (verde, ▲) y `neg` (rojo, ▼).
"""
from pathlib import Path
import base64
import html as _html

import charts as C
from profeco import ARCHIVO, FUENTE, URL_OFICIAL

FONT = dict(family="Segoe UI, system-ui, sans-serif", size=13, color=C.TEXT2)
CONFIG = {"displaylogo": False, "responsive": True, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def layout(**kw):
    base = dict(height=600, paper_bgcolor=C.FIG, plot_bgcolor=C.FIG, font=FONT,
                margin=dict(l=150, r=40, t=100, b=60),
                hoverlabel=dict(bgcolor=C.BOX, bordercolor=C.GRID, font=dict(color=C.TEXT)),
                legend=dict(bgcolor=C.BOX, bordercolor=C.GRID, borderwidth=1, font=dict(color=C.TEXT)))
    base.update(kw)
    return base


def title(text, sub=None):
    t = f"{text}<br><span style='font-size:12px;color:{C.TEXT2}'>{sub}</span>" if sub else text
    return dict(text=t, x=0.01, xanchor="left", y=0.985, yanchor="top", font=dict(size=17, color=C.TEXT))


def axis(**kw):
    base = dict(gridcolor=C.GRID, zeroline=False, linecolor=C.AXIS, tickfont=dict(color=C.TEXT2),
                title_font=dict(color=C.TEXT2))
    base.update(kw)
    return base


def pct(v, dec=1):
    """Delta en HTML con color y flecha por signo."""
    cls = "pos" if v > 0 else "neg" if v < 0 else ""
    arrow = "▲" if v > 0 else "▼" if v < 0 else "="
    return f"<span class='{cls}'>{arrow} {v:+.{dec}f}%</span>".replace("-", "−")


def fig_div(fig, div_id):
    return fig.to_html(full_html=False, include_plotlyjs=False, config=CONFIG, div_id=div_id)


def gallery(items):
    out = []
    for t, cap, img in items:
        b64 = base64.b64encode(Path(img).read_bytes()).decode("ascii")
        out.append(f'<figure class="card"><img loading="lazy" alt="{_html.escape(t)}" src="data:image/png;base64,{b64}">'
                   f'<figcaption><b>{t}.</b> {cap} <a class="dl" download="{Path(img).name}" href="#">Descargar PNG</a>'
                   "</figcaption></figure>")
    return "\n".join(out)


def table(headers, rows, cls=""):
    """Tabla con el estilo de la serie (encabezado azul, bordes, filas alternas). rows: listas de celdas HTML;
    una celda que empieza con «#» se centra como número."""
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td class='num'>{c[1:]}</td>" if str(c).startswith("#") else f"<td>{c}</td>"
                                    for c in r) + "</tr>" for r in rows)
    return f"<div class='card tbl {cls}'><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"


def page(titulo, descripcion, objetivo, h1, intro, stats, secciones, acciones, galeria, metodo,
         extra_head="", extra_js="", periodo="16 al 31 de agosto de 2026"):
    from plotly.offline import get_plotlyjs
    stats_html = "".join(f'<div class="stat"><b class="{c}">{v}</b><span>{t}</span></div>' for v, c, t in stats)
    secs = "".join(f"<h2>{h}</h2>\n<p>{p}</p>\n{body}\n" for h, p, body in secciones)
    acc = "".join(f"<li><b>{who}:</b> {what}</li>" for who, what in acciones)
    met = "".join(f"<li>{m}</li>" for m in metodo)
    return TEMPLATE.format(
        titulo=_html.escape(titulo), descripcion=_html.escape(descripcion), objetivo=objetivo, h1=h1, intro=intro,
        stats=stats_html, secciones=secs, acciones=acc, galeria=gallery(galeria), metodo=met, plotly=get_plotlyjs(),
        extra_head=extra_head, extra_js=extra_js, fuente=FUENTE, archivo=ARCHIVO, periodo=periodo,
        url=f"URL oficial del programa: <a href='{URL_OFICIAL}'>{URL_OFICIAL}</a>", firma=C.FIRMA, fig=C.FIG, box=C.BOX, grid=C.GRID, text=C.TEXT, text2=C.TEXT2,
        muted=C.MUTED, teal=C.TEAL, gold=C.GOLD, pos=C.GREEN_T, neg=C.RED_T)


def write(html, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(html, encoding="utf-8")
    return Path(path)


TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descripcion}">
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:{fig};color:{text};font:16px/1.6 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1280px;margin:0 auto;padding:40px 16px 72px}}
header.top{{border-left:5px solid {teal};padding-left:16px}}
.objetivo{{color:{text};font-size:1.02rem;margin:0 0 14px}}
h1{{font-size:clamp(1.6rem,3.4vw,2.4rem);line-height:1.2;margin:0 0 10px;font-weight:500}}
h1 b,h2 b{{font-weight:700}}
.pos{{color:{pos};font-weight:700}} .neg{{color:{neg};font-weight:700}}
h2{{font-size:1.3rem;margin:56px 0 6px;font-weight:500;border-left:4px solid {teal};padding-left:12px}}
p,li{{color:{text2};max-width:78ch}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:28px 0}}
.stat{{background:{box};border:1px solid {grid};border-radius:8px;padding:16px 18px}}
.stat b{{display:block;font-size:1.7rem;color:{text}}}
.stat span{{font-size:.86rem;color:{muted}}}
.card{{background:{box};border:1px solid {grid};border-radius:8px;padding:10px;margin-top:14px;overflow:hidden}}
figure{{margin:18px 0 0}} figure img{{display:block;max-width:100%;max-height:1150px;width:auto;height:auto;margin:0 auto;border-radius:4px}}
figcaption{{font-size:.88rem;color:{text2};padding:10px 4px 2px}} figcaption a{{color:{teal};margin-left:6px}}
.note{{background:{box};border:1px solid {grid};border-radius:8px;padding:14px 18px;margin-top:14px}}
table{{border-collapse:collapse;font-size:.9rem;font-variant-numeric:tabular-nums}}
td,th{{padding:9px 12px;border:1px solid #56627a;vertical-align:middle}}
th{{background:#2c4a6e;color:#fff;font-weight:700;text-align:center}}
tbody tr:nth-child(odd){{background:#1b212c}} tbody tr:nth-child(even){{background:{box}}}
.tbl{{overflow-x:auto;padding:0}} .tbl table{{width:100%;border:1px solid #56627a}}
td{{text-align:left}} td.num{{text-align:center;white-space:nowrap}} small{{color:{muted}}}
.search{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 4px}}
.search input,.search select{{flex:1 1 360px;background:{fig};color:{text};border:1px solid #56627a;border-radius:6px;padding:9px 12px;font:inherit}}
.search select{{flex:0 1 260px}}
footer{{margin-top:56px;font-size:.85rem;color:{muted};border-top:1px solid {grid};padding-top:16px}}
footer .firma{{display:block;margin-top:8px;color:{text2};font-weight:700}}
</style>
<script>{plotly}</script>
{extra_head}
</head><body><main>
<header class="top">
<p class="objetivo"><b>Objetivo.</b> {objetivo}</p>
<h1>{h1}</h1>
<p>{intro}</p>
</header>
<div class="stats">{stats}</div>
{secciones}
<h2>Qué hacer con esto</h2>
<div class="note"><ul>{acciones}</ul></div>
<h2>Galería</h2>
<p>Gráficas estáticas (PNG, 200 DPI).</p>
{galeria}
<h2>Método y límites</h2>
<div class="note"><ul>{metodo}</ul></div>
<footer>Fuente: elaboración propia con datos de {fuente}, archivo {archivo} ({periodo}); {url}
<span class="firma">{firma}</span></footer>
</main>
<script>
document.querySelectorAll('figure a.dl').forEach(a => {{ a.href = a.closest('figure').querySelector('img').src; }});
</script>
{extra_js}
</body></html>
"""
