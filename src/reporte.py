"""Reporte HTML del embudo de comparabilidad, con la plantilla del núcleo (reporte_base) y los textos de config.yaml.

Historia en cinco pasos (problema → a lo bruto → embudo → artefactos → lo que sobrevive → lo que falta), cada uno con
su gráfica y una lectura corta con deltas por signo: rojo ▼ = baja, verde ▲ = sube. Incluye un selector de producto.
"""
import json
import re
import html as _html

import numpy as np

import charts as C
import plantillas as PL
import reporte_base as RB
import embudo as M

CSS = f"""<style>
.gold{{color:{C.GOLD};font-weight:700}}
.stat b.neg{{color:{C.RED_T}}} .stat b.pos{{color:{C.GREEN_T}}} .stat b.gold{{color:{C.GOLD}}}
.stat span{{font-size:.92rem}}
.answer{{display:block;font-size:1.18rem;color:{C.TEXT};margin:4px 0 6px;max-width:80ch}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 4px 4px}}
.chip{{background:{C.FIG};border:1px solid #56627a;border-radius:999px;padding:5px 12px;font-size:.9rem;color:{C.TEXT2}}}
.chip b{{color:{C.TEXT}}}
.lectura{{margin:10px 6px 4px;padding-left:20px}} .lectura li{{margin:4px 0;color:{C.TEXT2}}}
.lectura li::marker{{color:{C.TEAL}}}
h2+p{{margin-top:2px}}
details.note summary{{cursor:pointer;color:{C.TEXT}}}
.acc li{{margin:6px 0}}
</style>"""


def _md(t):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def dpp(v, dec=1):
    """Delta en puntos con color y flecha por signo."""
    if abs(v) < 0.05:
        return "<span>= 0.0 pp</span>"
    cls, arrow = ("pos", "▲") if v > 0 else ("neg", "▼")
    return f"<span class='{cls}'>{arrow} {v:+.{dec}f} pp</span>".replace("-", "−")


def up(v, dec=0):
    return f"<span class='pos'>▲ {v:.{dec}f}%</span>"


def _fig_img(path, titulo, pie):
    return RB.gallery([(titulo, pie, path)])


def _lectura(puntos):
    return "" if not puntos else "<ul class='lectura'>" + "".join(f"<li>{p}</li>" for p in puntos) + "</ul>"


def build(cfg, v, res, prod, sob, casos, falta, sens, gallery, path):
    import plotly.graph_objects as go

    v = dict(v)
    x = prod.dropna(subset=["ingenua", "extremos"])
    v["delta_pp"] = v["validada"] - v["paso_ingenua"]
    v["pct_val_30"] = (x.extremos > 30).mean() * 100
    v["delta_30"] = v["pct_val_30"] - (x.ingenua > 30).mean() * 100
    cam = dict(zip(res.paso, res.cambio_pp))
    v["h_pres"], v["h_tiendas"] = dpp(cam["presentacion"]), dpp(cam["tiendas"])
    v["h_marca"], v["h_giro"] = dpp(cam["marca"]), dpp(cam["giro"])
    v["h_sobre_azar"] = dpp(v["validada"] - v["azar"])
    v["h_delta"] = dpp(v["delta_pp"])
    v["h_cad_sob"], v["h_cad_no"] = up(v["cadena_sobreviven"]), up(v["cadena_no_sobreviven"], 1)
    R_ = lambda t: _md(PL.render(t, v))
    rep = cfg["reporte"]
    charts = {g["archivo"]: g for g in cfg["graficas"]}
    root = path.parent.parent / "outputs/charts"
    nombres = res.nombre.tolist()
    pasos = res.paso.tolist()

    # --- embudo interactivo
    cols = [C.SAND] + [C.SLATE] * (len(res) - 1)
    fig = go.Figure(go.Bar(
        x=res.brecha_mediana, y=nombres, orientation="h",
        marker=dict(color=cols, line=dict(color=[C.FIG] * (len(res) - 1) + [C.TEXT], width=1.5)),
        text=[f"{a:.1f}%" for a in res.brecha_mediana], textposition="outside", textfont=dict(color=C.TEXT, size=13),
        customdata=np.c_[res.ic90_inf, res.ic90_sup],
        hovertemplate="<b>%{y}</b><br>%{x:.1f}% (IC90 %{customdata[0]:.1f}–%{customdata[1]:.1f})<extra></extra>", showlegend=False))
    fig.add_vline(v["azar"], line=dict(color=C.GOLD, width=2, dash="dash"),
                  annotation=dict(text=f"Azar: {v['azar']:.1f}%", font=dict(color=C.GOLD), yanchor="bottom"))
    fig.update_layout(**RB.layout(height=470, margin=dict(l=200, r=60, t=40, b=50)),
                      xaxis=RB.axis(title="Municipio caro típico frente al barato típico", ticksuffix="%", range=[0, 30]),
                      yaxis=RB.axis(autorange="reversed", tickfont=dict(size=13, color=C.TEXT)))
    chips = "".join(f"<span class='chip'><b>{r_.nombre}</b> {dpp(r_.cambio_pp)}</span>" for r_ in res.iloc[1:].itertuples())
    embudo_html = f"<div class='card'>{RB.fig_div(fig, 'embudo')}<div class='chips'>{chips}</div></div>"

    # --- tablas compactas
    t_art = RB.table(["Qué lo producía", "Producto", "Antes", "Después", "Cambio"],
                     [[f"<b>{c.tipo}</b>", c.producto, f"#{c.antes:.0f}%", f"#{c.despues:.0f}%", f"#{dpp(c.despues - c.antes, 0)}"]
                      for c in casos.itertuples()])
    rel = sob[sob.relevante].sort_values("brecha_pct", ascending=False).head(8)
    t_sob = RB.table(["Artículo", "Giro", "Diferencia", "IC90", "Barato → caro típico"],
                     [[f"<b>{c.etiqueta}</b>", M.giro_corto(c.giro).capitalize(), f"#{up(c.brecha_pct)}",
                       f"#{c.ic90_inf:.0f}–{c.ic90_sup:.0f}%", f"{c.mun_barato} {C.money(c.precio_barato)} → {c.mun_caro} {C.money(c.precio_caro)}"]
                      for c in rel.itertuples()])
    extra = {"03_casos_artefacto.png": t_art, "04_casos_sobreviven.png": t_sob}

    # --- historia
    secciones = []
    for h in rep["historia"]:
        g = h["grafica"]
        if g == "embudo":
            body = embudo_html
        else:
            gi = charts[g]
            body = _fig_img(root / g, PL.render(gi["titulo"], v), PL.render(gi["pie"], v)) + extra.get(g, "")
        body += _lectura([R_(p) for p in h.get("puntos", [])])
        secciones.append((R_(h["titulo"]), R_(h["frase"]), body))

    # --- selector de producto
    data = {k: {"v": [None if np.isnan(a) else round(float(a), 1) for a in row[pasos]],
                "az": None if np.isnan(row.get("azar_mediana", np.nan)) else round(float(row["azar_mediana"]), 1)}
            for k, row in prod.iterrows()}
    orden = sorted(data, key=lambda k: -(data[k]["v"][0] or 0))
    inicial = casos.producto.iloc[0] if casos.producto.iloc[0] in data else orden[0]
    opts = "".join(f"<option{' selected' if k == inicial else ''}>{_html.escape(k)}</option>" for k in orden)
    lay = RB.layout(height=420, margin=dict(l=200, r=60, t=30, b=40))
    lay.update(xaxis=RB.axis(ticksuffix="%", rangemode="tozero"), yaxis=RB.axis(autorange="reversed", tickfont=dict(size=13, color=C.TEXT)))
    sel_html = (f"<div class='card'><div class='search'><label for='sel'><b>Producto:</b></label><select id='sel'>{opts}</select></div>"
                "<p id='prodtxt' style='margin:4px 8px'></p><div id='prodfig'></div></div>")
    secciones.append(("Explore un <b>producto</b>", "Ordenados de mayor a menor diferencia a lo bruto.", sel_html))
    js = f"""<script>
const DATA = {json.dumps(data, ensure_ascii=False)};
const STEPS = {json.dumps(nombres, ensure_ascii=False)};
const LAY = {json.dumps(lay)};
const COL = {json.dumps(cols)};
function fmt(x) {{ return x.toFixed(1).replace('-', '−'); }}
function draw(p) {{
  const d = DATA[p];
  const tx = d.v.map(x => x === null ? 'sin datos' : fmt(x) + '%');
  const shapes = d.az === null ? [] : [{{type:'line', x0:d.az, x1:d.az, yref:'paper', y0:0, y1:1, line:{{color:'{C.GOLD}', width:2, dash:'dash'}}}}];
  Plotly.react('prodfig', [{{type:'bar', orientation:'h', y:STEPS, x:d.v.map(x => x === null ? 0 : x), text:tx, textposition:'outside',
    textfont:{{color:'{C.TEXT}'}}, marker:{{color:COL}}, hovertemplate:'%{{y}}: %{{text}}<extra></extra>'}}], Object.assign({{}}, LAY, {{shapes: shapes}}), {json.dumps(RB.CONFIG)});
  const a = d.v[0], z = d.v[d.v.length - 1], dz = z - a;
  const cls = dz < 0 ? 'neg' : 'pos', ar = dz < 0 ? '▼' : '▲';
  let t = '<b>' + p + '</b>: ' + fmt(a) + '% a lo bruto → <b>' + fmt(z) + '%</b> validada <span class="' + cls + '">' + ar + ' ' + (dz > 0 ? '+' : '') + fmt(dz) + ' pp</span>';
  if (d.az !== null) t += ' · azar <span class="gold">' + fmt(d.az) + '%</span>';
  document.getElementById('prodtxt').innerHTML = t;
}}
document.getElementById('sel').addEventListener('change', e => draw(e.target.value));
draw(document.getElementById('sel').value);
</script>"""

    acciones = [(aud, R_(t)) for aud, t in rep["acciones_cortas"].items()]
    intro = f"<span class='answer'>{R_(rep['h1'])}</span><small>{R_(rep['intro'])}</small>"
    html = RB.page(
        titulo=cfg["titulo"], descripcion=PL.render(rep["descripcion"], v), objetivo=R_(cfg["objetivo"]), h1=R_(rep["problema"]),
        intro=intro, stats=[(R_(s["valor"]), s.get("clase", ""), R_(s["texto"])) for s in rep["stats"]],
        secciones=secciones, acciones=acciones, galeria=[], metodo=[R_(m) for m in rep["metodo"]], extra_head=CSS, extra_js=js)
    # Sin galería aparte (cada gráfica va en su paso) y método plegado.
    html = html.replace("<h2>Galería</h2>\n<p>Gráficas estáticas (PNG, 200 DPI).</p>\n\n", "")
    html = html.replace('<h2>Método y límites</h2>\n<div class="note"><ul>',
                        "<h2>Método y límites</h2>\n<details class='note'><summary>Ver método</summary><ul>")
    html = html.replace("</ul></div>\n<footer>", "</ul></details>\n<footer>")
    return RB.write(html, path)
