"""GIF corto (≈36 s, 960×960) con la historia del análisis, para acompañar una publicación.

Escenas: pregunta → a lo bruto → embudo paso a paso → caso almendras → lo que sobrevive → cierre con firma.
Notas con letra manuscrita, ligeramente inclinadas, y subrayados a mano alzada.
Uso: python src/gif_historia.py  → outputs/social/historia_embudo.gif
"""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import charts as C  # noqa: E402

W = H = 960
DPI = 100
HAND = "Ink Free"
rng = np.random.default_rng(7)
R = {k: v["cifra"] for k, v in json.loads((ROOT / "data/processed/resultados.json").read_text(encoding="utf-8")).items()}
RES = pd.read_csv(ROOT / "data/processed/embudo.csv", encoding="utf-8-sig")
CH = ROOT / "outputs/charts"
frames = []   # (imagen PIL, duración ms)


def fig_new():
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_facecolor(C.FIG)
    return fig


def grab(fig, ms):
    fig.canvas.draw()
    img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy())
    plt.close(fig)
    frames.append((img, ms))


def hand(fig, x, y, s, size=26, color=C.GOLD, rot=None, ha="left", **kw):
    fig.text(x, y, s, fontfamily=HAND, fontsize=size, color=color, ha=ha, va="center",
             rotation=rng.uniform(-2.5, 2.5) if rot is None else rot, **kw)


def scribble(fig, x0, x1, y, color=C.GOLD, lw=3):
    """Subrayado a mano alzada: línea con temblor."""
    xs = np.linspace(x0, x1, 40)
    ys = y + np.cumsum(rng.normal(0, 0.0012, 40)) + np.linspace(0, rng.uniform(-0.006, 0.006), 40)
    fig.add_artist(plt.Line2D(xs, ys, transform=fig.transFigure, color=color, lw=lw, solid_capstyle="round", alpha=0.9))


def title(fig, s, y=0.93, size=27, color=C.TEXT, weight="bold"):
    fig.text(0.06, y, s, fontsize=size, color=color, fontweight=weight, va="top", fontfamily="Segoe UI")


def chart(fig, name, rect):
    img = plt.imread(CH / name)
    ax = fig.add_axes(rect)
    ax.imshow(img)
    ax.axis("off")


def firma(fig):
    fig.text(0.5, 0.035, C.FIRMA, ha="center", fontsize=10.5, color=C.TEXT2, fontfamily="Segoe UI")


# ----------------------------------------------------------------------------- 1. la pregunta
q = "«Este producto cuesta 25% más\nen otra ciudad»"
for k in range(6, len(q) + 1, 6):
    fig = fig_new()
    fig.text(0.06, 0.70, "Un reporte dice:", fontsize=26, color=C.TEXT2, fontfamily="Segoe UI")
    fig.text(0.06, 0.62, q[:k], fontsize=30, va="top", color=C.TEXT, fontweight="bold", fontfamily="Segoe UI")
    grab(fig, 90)
for ms, extra in [(800, False), (2300, True)]:
    fig = fig_new()
    fig.text(0.06, 0.70, "Un reporte dice:", fontsize=26, color=C.TEXT2, fontfamily="Segoe UI")
    fig.text(0.06, 0.62, q, fontsize=30, va="top", color=C.TEXT, fontweight="bold", fontfamily="Segoe UI")
    if extra:
        hand(fig, 0.08, 0.36, "¿es una oportunidad?", size=46, rot=-3)
        scribble(fig, 0.08, 0.80, 0.31)
        fig.text(0.06, 0.18, "Precios de PROFECO · 72 municipios · 16–31 ago 2026", fontsize=15, color=C.MUTED,
                 fontfamily="Segoe UI")
    grab(fig, ms)

# ----------------------------------------------------------------------------- 2. a lo bruto
fig = fig_new()
title(fig, "1. A lo bruto, todo parece oportunidad")
chart(fig, "02_distribucion_ingenua_validada.png", [0.03, 0.22, 0.94, 0.62])
hand(fig, 0.08, 0.15, f"{R['pct_ingenua_30']:.0f}% de los productos «cuesta» +30% en otra ciudad", size=24, color=C.TEXT)
grab(fig, 2800)
fig = fig_new()
title(fig, "1. A lo bruto, todo parece oportunidad")
chart(fig, "02_distribucion_ingenua_validada.png", [0.03, 0.22, 0.94, 0.62])
hand(fig, 0.08, 0.15, f"{R['pct_ingenua_30']:.0f}% de los productos «cuesta» +30% en otra ciudad", size=24, color=C.TEXT)
hand(fig, 0.30, 0.08, "comparando lo mismo... ¿cuánto queda?", size=24, color=C.GOLD)
grab(fig, 2100)

# ----------------------------------------------------------------------------- 3. el embudo, paso a paso
labels = ["A lo bruto", "Misma presentación", "Mismo artículo", "Mismo giro", "3+ tiendas", "Mismo día", "Sin errores"]
vals = RES.brecha_mediana.tolist()
cambios = RES.cambio_pp.tolist()


def embudo_frame(n, azar=False, nota=False, ms=1100):
    fig = fig_new()
    title(fig, "2. Al comparar lo mismo, la diferencia se encoge", size=25)
    ax = fig.add_axes([0.31, 0.14, 0.46, 0.66])
    ax.set_facecolor(C.FIG)
    for i in range(len(labels)):
        if i >= n:
            continue
        col = C.SAND if i == 0 else C.SLATE
        ax.barh(i, vals[i], height=0.6, color=col, edgecolor=C.TEXT if i == len(labels) - 1 else "none", lw=1.5)
        ax.text(vals[i] + 0.5, i, f"{vals[i]:.1f}%", va="center", fontsize=15, color=C.TEXT, fontweight="bold")
        if i > 0 and abs(cambios[i]) >= 0.05:
            c = C.RED_T if cambios[i] < 0 else C.GREEN_T
            a = "▼" if cambios[i] < 0 else "▲"
            ax.text(1.24, i, f"{a} {cambios[i]:+.1f} pp".replace("-", "−"), va="center", ha="right", fontsize=14,
                    color=c, fontweight="bold", transform=ax.get_yaxis_transform())
    for i, l in enumerate(labels):
        ax.text(-0.6, i, l, ha="right", va="center", fontsize=15, color=C.TEXT if i < n else C.GRID, fontweight="bold")
    if azar:
        ax.axvline(R["azar"], color=C.GOLD, lw=2.2, ls=(0, (5, 4)))
    ax.set(xlim=(0, 30), ylim=(len(labels) - 0.5, -0.6), yticks=[], xticks=[0, 10, 20, 30])
    ax.tick_params(colors=C.TEXT2, labelsize=12)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    if azar:
        hand(fig, 0.36, 0.86, f"<-- esto daría el puro azar ({R['azar']:.1f}%)", size=22, color=C.GOLD)
    if nota:
        hand(fig, 0.10, 0.07, f"de {vals[0]:.0f}% a {vals[-1]:.1f}%: desaparece {R['desaparece_pct']:.0f}%", size=27,
             color=C.RED_T, rot=-1.5)
    grab(fig, ms)


for n in range(1, len(labels) + 1):
    embudo_frame(n, ms=1300 if n in (2, 5) else 900)
embudo_frame(len(labels), azar=True, ms=2200)
embudo_frame(len(labels), azar=True, nota=True, ms=2900)

# ----------------------------------------------------------------------------- 4. cómo nace una diferencia falsa
for paso in range(3):
    fig = fig_new()
    title(fig, "3. Cómo nace una diferencia falsa")
    fig.text(0.06, 0.74, "Almendras", fontsize=40, color=C.TEXT, fontweight="bold", fontfamily="Segoe UI")
    fig.text(0.06, 0.64, f"a lo bruto: {R['art1_ingenua']:.0f}% más cara en otro municipio", fontsize=24, color=C.TEXT2,
             fontfamily="Segoe UI")
    if paso >= 1:
        hand(fig, 0.08, 0.50, "Monterrey: bolsa de 1 kg", size=30, color=C.TEXT)
        hand(fig, 0.08, 0.42, "Lerma: bolsa de 75 g", size=30, color=C.TEXT)
        scribble(fig, 0.08, 0.62, 0.385, color=C.RED_T, lw=2.5)
    if paso >= 2:
        fig.text(0.06, 0.25, f"misma presentación: {R['art1_despues']:.0f}%", fontsize=30, color=C.TEXT, fontweight="bold",
                 fontfamily="Segoe UI")
        fig.text(0.06, 0.17, f"▼ {R['art1_despues'] - R['art1_antes']:+.0f} pp".replace("-", "−"), fontsize=30,
                 color=C.RED_T, fontweight="bold", fontfamily="Segoe UI")
        hand(fig, 0.55, 0.17, "no era precio, era tamaño", size=26, color=C.GOLD)
    grab(fig, [1400, 1900, 2700][paso])

# ----------------------------------------------------------------------------- 5. lo que sobrevive
fig = fig_new()
title(fig, "4. Lo que sí sobrevive")
chart(fig, "04_casos_sobreviven.png", [0.03, 0.17, 0.94, 0.70])
grab(fig, 1800)
fig = fig_new()
title(fig, "4. Lo que sí sobrevive")
chart(fig, "04_casos_sobreviven.png", [0.03, 0.17, 0.94, 0.70])
hand(fig, 0.07, 0.11, f"solo {R['n_relevantes']:.0f} de {R['n_articulos']:,.0f}: refrescos, cerveza, tortilla, frescos",
     size=24, color=C.GREEN_T)
grab(fig, 2900)

# ----------------------------------------------------------------------------- 6. cierre
for paso in range(2):
    fig = fig_new()
    fig.text(0.06, 0.74, "Una diferencia de precio", fontsize=34, color=C.TEXT, fontweight="bold", fontfamily="Segoe UI")
    fig.text(0.06, 0.66, "es una pregunta,", fontsize=34, color=C.TEXT, fontweight="bold", fontfamily="Segoe UI")
    fig.text(0.06, 0.58, "no una oportunidad.", fontsize=34, color=C.GOLD, fontweight="bold", fontfamily="Segoe UI")
    scribble(fig, 0.06, 0.62, 0.545)
    if paso:
        hand(fig, 0.08, 0.40, "antes de decidir, faltan:", size=28, color=C.TEXT2)
        hand(fig, 0.12, 0.31, "costos · márgenes · volumen", size=32, color=C.TEXT)
        firma(fig)
    grab(fig, [1600, 3900][paso])

# ----------------------------------------------------------------------------- guardar
total = sum(ms for _, ms in frames) / 1000
out = ROOT / "outputs/social/historia_embudo.gif"
pal = [f.convert("RGB").quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f, _ in frames]
pal[0].save(out, save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames], loop=0, optimize=True, disposal=1)
print(f"{out.name}: {len(frames)} cuadros, {total:.1f} s, {out.stat().st_size / 1e6:.1f} MB")
