"""GIF vertical (1080×1350, ≤20 s) con la historia del análisis, hecho con figuras de Plotly y los datos del proyecto.

Cinco cuadros, una idea cada uno: a lo bruto → la escalera de validación → por qué pasaba (almendras) → lo que queda
→ cierre. Mismo diseño en todos: fondo, título con la conclusión, subtítulo de una línea, gris para el contexto,
dorado para lo que importa, rojo para lo que baja, una sola anotación con flecha y la fuente abajo.
Cada cuadro se guarda también como PNG (outputs/social/cuadro_0X_*.png) para carrusel.
Uso: python src/gif_historia.py
Requiere kaleido (exportación de Plotly a PNG).
"""
from pathlib import Path
import json
import re
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import charts as C  # noqa: E402
import embudo as M  # noqa: E402

W, H = 1080, 1350
OUT = ROOT / "outputs/social"
PROC = ROOT / "data/processed"
BG, GRID, TXT, TXT2 = C.FIG, "#2f3747", C.TEXT, C.TEXT2
GRAY, GRAY_D, GOLD, RED, GREEN = "#7d8697", "#3d4556", C.GOLD, C.RED_T, C.GREEN_T
FONT = "Segoe UI, Arial, sans-serif"
TITLE_PX, SUB_PX, AX_PX, NOTE_PX, FOOT_PX = 40, 25, 24, 24, 19
FUENTE = "Fuente: PROFECO, Quién es Quién en los Precios, 16-31 ago 2026 · Ernesto Roldán · Python + Plotly"

R = {k: v["cifra"] for k, v in json.loads((PROC / "resultados.json").read_text(encoding="utf-8")).items()}
RES = pd.read_csv(PROC / "embudo.csv", encoding="utf-8-sig")
PROD = pd.read_csv(PROC / "brecha_producto_paso.csv", encoding="utf-8-sig").dropna(subset=["ingenua", "extremos"])
SOB = pd.read_csv(PROC / "sobrevivientes.csv", encoding="utf-8-sig")
P30_ING = (PROD.ingenua > 30).mean() * 100
P30_VAL = (PROD.extremos > 30).mean() * 100


def layout(fig, title, sub, l=60, t=275, b=150, legend=False):
    fig.update_layout(
        width=W, height=H, paper_bgcolor=BG, plot_bgcolor=BG, showlegend=legend,
        font=dict(family=FONT, size=AX_PX, color=TXT2),
        margin=dict(l=l, r=50, t=t, b=b),
        title=dict(text=f"<b>{title}</b><br><span style='font-size:{SUB_PX}px;color:{TXT2}'>{sub}</span>",
                   x=0.045, xanchor="left", y=0.958, yanchor="top", font=dict(size=TITLE_PX, color=TXT, family=FONT)),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", font=dict(size=AX_PX, color=TXT2),
                    bgcolor="rgba(0,0,0,0)"),
    )
    fig.add_annotation(text=FUENTE, xref="paper", yref="paper", x=0, y=0, xanchor="left", yanchor="top",
                       xshift=-(l - 50), yshift=-(b - 55), showarrow=False, font=dict(size=FOOT_PX, color=C.MUTED))
    return fig


def note(fig, x, y, text, ax, ay, xref="x", yref="y", xanchor="auto"):
    """La única anotación del cuadro: flecha al dato clave."""
    fig.add_annotation(x=x, y=y, xref=xref, yref=yref, text=text, showarrow=True, arrowhead=2, arrowsize=1.3,
                       arrowwidth=2.5, arrowcolor=GOLD, ax=ax, ay=ay, align="left", xanchor=xanchor, font=dict(size=NOTE_PX, color=GOLD),
                       bgcolor=BG, borderpad=4)


def axis(**kw):
    base = dict(gridcolor=GRID, zeroline=False, linecolor=GRAY_D, tickfont=dict(size=AX_PX, color=TXT2),
                title_font=dict(size=AX_PX, color=TXT2))
    base.update(kw)
    return base


def delta(v, dec=1):
    return (f"▲ +{v:.{dec}f}" if v > 0 else f"▼ −{abs(v):.{dec}f}") + " pts"


# ----------------------------------------------------------------------------- 1. a lo bruto (vista previa)
def cuadro_bruto():
    bins = [0, 10, 20, 30, 50, 100, 10000]
    lab = ["0–10%", "10–20%", "20–30%", "30–50%", "50–100%", "más de 100%"]
    hi = pd.cut(PROD.ingenua, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
    hv = pd.cut(PROD.extremos, bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
    fig = go.Figure()
    fig.add_bar(x=lab, y=hv, name="Comparando el mismo artículo", marker_color=GRAY_D,
                text=[f"{v:.0f}%" for v in hv], textposition="outside", textfont=dict(size=AX_PX, color=GRAY))
    fig.add_bar(x=lab, y=hi, name="A lo bruto (dorado: más de 30%)", marker_color=[GRAY] * 3 + [GOLD] * 3,
                text=[f"{v:.0f}%" for v in hi], textposition="outside", textfont=dict(size=AX_PX, color=TXT))
    fig.add_vline(x=2.5, line=dict(color=GOLD, width=2, dash="dash"))
    layout(fig, f"A lo bruto, {P30_ING:.0f}% de los productos parece<br>+30% más caro en otro municipio",
           "Barras: % de productos según cuánto más cuesta en el municipio caro", legend=True)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
                      xaxis=axis(title="Diferencia entre el municipio caro y el barato típicos", tickangle=0),
                      yaxis=axis(title="% de productos", ticksuffix="%", range=[0, max(hi.max(), hv.max()) * 1.25]))
    note(fig, 3.2, hi.iloc[3] + 1.5, f"{P30_ING:.0f}% a lo bruto<br>vs. {P30_VAL:.0f}% al comparar lo mismo", 40, -190)
    return fig


# ----------------------------------------------------------------------------- 2 y 5. escalera
LAB = ["A lo bruto", "Misma presentación", "Mismo artículo", "Mismo giro", "3+ tiendas", "Mismo día", "Sin errores"]


def cuadro_escalera(n, title, sub, nota):
    vals, cam = RES.brecha_mediana.tolist(), RES.cambio_pp.tolist()
    k = len(LAB)
    x = [vals[i] if i < n else None for i in range(k)]
    col = [GRAY if i < k - 1 else GOLD for i in range(k)]
    fig = go.Figure(go.Bar(x=x, y=LAB, orientation="h", marker_color=col, text=[f"{v:.1f}%" if v else "" for v in x],
                           textposition="outside", textfont=dict(size=26, color=TXT), cliponaxis=False))
    dtxt = [delta(cam[i]) if (0 < i < n and abs(cam[i]) >= 0.05) else "" for i in range(k)]
    dcol = [RED if c < 0 else GREEN for c in cam]
    fig.add_trace(go.Scatter(x=[33.5] * k, y=LAB, mode="text", text=dtxt, textposition="middle left",
                             textfont=dict(size=AX_PX, color=dcol), hoverinfo="skip", cliponaxis=False))
    fig.add_vline(x=R["azar"], line=dict(color=GRAY, width=2, dash="dot"))
    layout(fig, title, sub, l=280)
    fig.update_layout(xaxis=axis(range=[0, 34], ticksuffix="%", dtick=10, title="Diferencia típica entre municipios"),
                      yaxis=axis(range=[k + 0.5, -0.6], tickfont=dict(size=AX_PX + 2, color=TXT), gridcolor="rgba(0,0,0,0)"),
                      bargap=0.35)
    if nota:
        note(fig, vals[-1] * 0.55, LAB[-1], nota, 260, 100)
    return fig


# ----------------------------------------------------------------------------- 3. almendras
def cuadro_almendras():
    d = M.prep(pd.read_parquet(PROC / "profeco_extracto.parquet", columns=M.COLS))
    a = d[d.producto == "Almendras"].groupby("pres_key").precio_num.mean().sort_values()
    lab = [M.presentacion_corta(k) for k in a.index]
    col = [GOLD if k in (a.index[0], a.index[-1]) else GRAY for k in a.index]
    fig = go.Figure(go.Bar(x=lab, y=a.values, marker_color=col, text=[C.money(v) for v in a.values], textposition="outside",
                           textfont=dict(size=30, color=TXT), cliponaxis=False))
    layout(fig, f"Almendras: {R['art1_ingenua']:.0f}% más caras… porque<br>se comparaba 1 kg contra 75 g",
           "Precio promedio de cada presentación, todos los municipios")
    fig.update_layout(xaxis=axis(title="Presentación", tickfont=dict(size=28, color=TXT)),
                      yaxis=axis(title="Precio promedio", tickprefix="$", range=[0, a.max() * 1.25]), bargap=0.35)
    note(fig, lab[-1], a.values[-1] * 0.62, "Monterrey registra sobre todo 1 kg;<br>Lerma, solo la bolsa de 75 g.<br>"
         f"Con la misma presentación: {R['art1_despues']:.0f}%", -330, -40)
    return fig


# ----------------------------------------------------------------------------- 4. lo que sobrevive
def corto(r):
    p, m, pres = r.producto, M.marca_corta(r.marca), str(r.presentacion).lower()
    pack = re.search(r"(\d+)\s+(latas|botellas)", pres)
    if p == "Refresco":
        return f"{m} {M.presentacion_corta(r.pres_key)}"
    if p == "Cerveza":
        return f"Cerveza {m}" + (f" {pack.group(1)} {pack.group(2)}" if pack else "")
    if p.startswith("Tortilla"):
        return "Tortilla (" + ("tortillería" if "Tortiller" in str(r.giro) else "súper") + ")"
    if p == "Alimentos Preparados":
        return f"Sopa {m} {M.presentacion_corta(r.pres_key)}"
    if p.startswith("Agua"):
        return f"Agua {m} {M.presentacion_corta(r.pres_key)}"
    especial = {"Lechuga": "Lechuga romana", "Pan Blanco Bolillo": "Bolillo", "Limón": "Limón persa"}
    return especial.get(p, f"{p} {m}".strip())


def cuadro_sobrevive():
    rel = SOB[SOB.relevante].sort_values("p_valor")
    pick = rel.drop_duplicates("familia")
    s = pd.concat([pick, rel.drop(pick.index)]).head(10).sort_values("brecha_pct")
    names = [corto(r) for r in s.itertuples()]
    fig = go.Figure()
    fig.add_bar(x=s.brecha_pct, y=names, orientation="h", name="Diferencia real", marker_color=GOLD,
                text=[f"{v:.0f}%" for v in s.brecha_pct], textposition="outside", textfont=dict(size=AX_PX, color=TXT),
                cliponaxis=False)
    fig.add_trace(go.Scatter(x=s.azar_mediana, y=names, mode="markers", name="Lo que daría el azar",
                             marker=dict(symbol="line-ns", size=30, line=dict(width=4, color=GRAY))))
    layout(fig, f"Solo {R['n_relevantes']:.0f} de {R['n_articulos']:,.0f} productos tienen una<br>diferencia real y relevante",
           f"Diferencia entre el municipio caro y el barato · 10 de los {R['n_relevantes']:.0f}", l=330, legend=True)
    fig.update_layout(xaxis=axis(range=[0, 60], ticksuffix="%", dtick=10), bargap=0.3,
                      yaxis=axis(tickfont=dict(size=AX_PX, color=TXT), gridcolor="rgba(0,0,0,0)"))
    t = s[s.producto.str.startswith("Tortilla") & s.giro.str.contains("Tortiller")].iloc[0]
    note(fig, t.brecha_pct, corto(t), ("La misma tortilla:<br>" + f"{C.money(t.precio_barato)} en {t.mun_barato}<br>"
         + f"{C.money(t.precio_caro)} en Benito Juárez (Q. Roo)").replace("$", "&#36;"), 88, 790, xanchor="right")
    return fig


# ----------------------------------------------------------------------------- armar
def main():
    for f in OUT.glob("carrusel_0*.png"):
        f.unlink()
    T2 = f"Al comparar lo mismo, la diferencia típica<br>baja de {RES.brecha_mediana.iloc[0]:.0f}% a {R['validada']:.1f}%"
    S2 = "Cada barra agrega un filtro · línea punteada: lo que daría el azar"
    N2 = f"{R['validada']:.1f}%: casi lo que daría<br>el azar ({R['azar']:.1f}%)"
    plan = [
        ("cuadro_01_a_lo_bruto.png", cuadro_bruto(), 3200),
        (None, cuadro_escalera(1, T2, S2, None), 1000),
        (None, cuadro_escalera(3, T2, S2, None), 1000),
        (None, cuadro_escalera(5, T2, S2, None), 1000),
        ("cuadro_02_escalera.png", cuadro_escalera(7, T2, S2, N2), 2500),
        ("cuadro_03_almendras.png", cuadro_almendras(), 3300),
        ("cuadro_04_lo_que_sobrevive.png", cuadro_sobrevive(), 3500),
        ("cuadro_05_cierre.png", cuadro_escalera(7, "Una diferencia de precio es una pregunta,<br>no una oportunidad",
                                                 "Antes de decidir faltan costos, márgenes y volumen",
                                                 "Lo que queda: una pregunta<br>para revisar con datos propios"), 4000),
    ]
    frames = []
    tmp = OUT / "_tmp_cuadro.png"
    for name, fig, ms in plan:
        path = OUT / name if name else tmp
        fig.write_image(path, width=W, height=H, scale=1)
        frames.append((Image.open(path).convert("RGB"), ms))
    tmp.unlink(missing_ok=True)
    total = sum(ms for _, ms in frames) / 1000
    assert total <= 20, total
    gif = OUT / "historia_embudo.gif"
    pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f, _ in frames]
    pal[0].save(gif, save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames], loop=0, optimize=True)
    print(f"{gif.name}: {len(frames)} cuadros, {total:.1f} s, {gif.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
