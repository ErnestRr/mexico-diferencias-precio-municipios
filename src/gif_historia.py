"""GIF vertical (1080×1350, ≤20 s) con la historia del análisis y sus cuadros clave en PNG para carrusel.

Cuadros: pregunta → a lo bruto → escalera de validación → almendras → lo que sobrevive → cierre.
Todas las cifras salen de data/processed/ (resultados.json, embudo.csv, brecha_producto_paso.csv, sobrevivientes.csv).
Reglas de lectura en celular: ningún texto menor a 28 px (salvo «Python · Plotly», 22 px) y títulos de 56 px o más.
Uso: python src/gif_historia.py → outputs/social/historia_embudo.gif y outputs/social/carrusel_0X_*.png
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

W, H, DPI = 1080, 1350, 100
PT = 72 / DPI                     # puntos por píxel
MIN_PX, TITLE_PX, SMALL_PX = 28, 56, 22
HAND, SANS = "Ink Free", "Segoe UI"
OUT = ROOT / "outputs/social"
rng = np.random.default_rng(11)

PROC = ROOT / "data/processed"
R = {k: v["cifra"] for k, v in json.loads((PROC / "resultados.json").read_text(encoding="utf-8")).items()}
RES = pd.read_csv(PROC / "embudo.csv", encoding="utf-8-sig")
PROD = pd.read_csv(PROC / "brecha_producto_paso.csv", encoding="utf-8-sig").dropna(subset=["ingenua", "extremos"])
SOB = pd.read_csv(PROC / "sobrevivientes.csv", encoding="utf-8-sig")
P30_ING = (PROD.ingenua > 30).mean() * 100
P30_VAL = (PROD.extremos > 30).mean() * 100

frames = []


def px(size_px):
    return size_px * PT


def T(fig, x, y, s, size_px, color=C.TEXT, bold=False, family=SANS, small_ok=False, **kw):
    """Texto en el lienzo con tamaño en píxeles; impide textos menores a 28 px."""
    assert size_px >= (SMALL_PX if small_ok else MIN_PX), f"texto de {size_px}px: «{s}»"
    kw.setdefault("va", "center")
    return fig.text(x, y, s, fontsize=px(size_px), color=color, fontweight="bold" if bold else "normal",
                    fontfamily=family, **kw)


def hand(fig, x, y, s, size_px=40, color=C.GOLD, rot=None, **kw):
    return T(fig, x, y, s, size_px, color=color, family=HAND, rotation=rng.uniform(-2, 2) if rot is None else rot, **kw)


def scribble(fig, x0, x1, y, color=C.GOLD, lw=4):
    xs = np.linspace(x0, x1, 40)
    ys = y + np.cumsum(rng.normal(0, 0.0009, 40)) + np.linspace(0, rng.uniform(-0.004, 0.004), 40)
    fig.add_artist(plt.Line2D(xs, ys, transform=fig.transFigure, color=color, lw=lw, solid_capstyle="round", alpha=0.9))


def title(fig, s, y=0.935):
    T(fig, 0.065, y, s, 60, bold=True, va="top", linespacing=1.15)


def new():
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI)
    fig.patch.set_facecolor(C.FIG)
    return fig


def grab(fig, ms, png=None):
    if png:
        fig.savefig(OUT / png, dpi=DPI, facecolor=C.FIG)
    fig.canvas.draw()
    frames.append((Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()), ms))
    plt.close(fig)


def pct(v, dec=0):
    return f"{v:.{dec}f}%"


def delta(v, dec=1, suf=" pp"):
    return (f"▲ {v:+.{dec}f}" if v > 0 else f"▼ {v:+.{dec}f}").replace("-", "−") + suf


# ----------------------------------------------------------------------------- 1. pregunta (sin animación: vista previa)
fig = new()
T(fig, 0.065, 0.80, "Un reporte dice:", 40, color=C.TEXT2)
T(fig, 0.065, 0.735, f"«Este producto cuesta\n{R['paso_ingenua']:.0f}% más en otra\nciudad»", 76, bold=True, va="top", linespacing=1.15)
hand(fig, 0.075, 0.38, "¿es una oportunidad?", 84, rot=-3)
scribble(fig, 0.075, 0.90, 0.325)
T(fig, 0.065, 0.12, f"Precios de PROFECO · {R['productos_universo']:.0f} productos\n72 municipios · 16–31 ago 2026", 30,
  color=C.MUTED, va="top", linespacing=1.3)
grab(fig, 2500, "carrusel_01_pregunta.png")

# ----------------------------------------------------------------------------- 2. a lo bruto
fig = new()
title(fig, "1. A lo bruto, todo\nparece oportunidad")
T(fig, 0.065, 0.58, pct(P30_ING), 190, bold=True, color=C.SAND)
T(fig, 0.47, 0.58, "→", 120, color=C.TEXT2)
T(fig, 0.60, 0.58, pct(P30_VAL), 190, bold=True, color=C.TEXT)
T(fig, 0.065, 0.43, "de los productos parecían costar\n+30% más en otro municipio", 44, color=C.TEXT, va="top", linespacing=1.25)
T(fig, 0.065, 0.24, delta(P30_VAL - P30_ING, 0), 64, bold=True, color=C.RED_T)
hand(fig, 0.42, 0.24, "al comparar el\nmismo artículo", 44, color=C.GOLD)
grab(fig, 2500)

# ----------------------------------------------------------------------------- 3. escalera
labels = ["A lo bruto", "Misma presentación", "Mismo artículo", "Mismo giro", "3+ tiendas", "Mismo día", "Sin errores"]
vals, cam = RES.brecha_mediana.tolist(), RES.cambio_pp.tolist()


def escalera(n, ms, png=None):
    fig = new()
    title(fig, "2. Al comparar lo mismo,\nla diferencia se encoge")
    ax = fig.add_axes([0.40, 0.20, 0.36, 0.56])
    ax.set_facecolor(C.FIG)
    for i, lab in enumerate(labels):
        on = i < n
        ax.text(-0.04, i, lab, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=px(34),
                fontweight="bold", color=C.TEXT if on else C.GRID, fontfamily=SANS)
        if not on:
            continue
        ax.barh(i, vals[i], height=0.62, color=C.SAND if i == 0 else C.SLATE,
                edgecolor=C.TEXT if i == len(labels) - 1 else "none", lw=2)
        ax.text(vals[i] + 0.6, i, f"{vals[i]:.1f}%", va="center", fontsize=px(32), fontweight="bold", color=C.TEXT,
                fontfamily=SANS)
        if i and abs(cam[i]) >= 0.05:
            ax.text(1.38, i, delta(cam[i]), transform=ax.get_yaxis_transform(), ha="right", va="center",
                    fontsize=px(30), fontweight="bold", color=C.RED_T if cam[i] < 0 else C.GREEN_T, fontfamily=SANS)
    if n == len(labels):
        ax.axvline(R["azar"], color=C.GOLD, lw=3, ls=(0, (6, 5)))
        hand(fig, 0.40, 0.80, f"- - - lo que daría el azar: {R['azar']:.1f}%", 38, color=C.GOLD, rot=0)
        hand(fig, 0.065, 0.11, f"de {vals[0]:.0f}% a {vals[-1]:.1f}%: desaparece {R['desaparece_pct']:.0f}%", 52,
             color=C.RED_T, rot=-1.5)
    ax.set(xlim=(0, 30), ylim=(len(labels) - 0.5, -0.6), yticks=[], xticks=[])
    for s in ax.spines.values():
        s.set_visible(False)
    grab(fig, ms, png)


escalera(1, 500)
escalera(4, 500)
escalera(len(labels), 3000, "carrusel_02_escalera.png")

# ----------------------------------------------------------------------------- 4. almendras
fig = new()
title(fig, "3. Cómo nace una\ndiferencia falsa")
T(fig, 0.065, 0.66, "Almendras", 96, bold=True)
T(fig, 0.065, 0.585, f"a lo bruto: {R['art1_ingenua']:.0f}% más caras\nen otro municipio", 44, color=C.TEXT2, va="top",
  linespacing=1.25)
hand(fig, 0.08, 0.43, "Monterrey: bolsa de 1 kg", 54, color=C.TEXT)
hand(fig, 0.08, 0.355, "Lerma: bolsa de 75 g", 54, color=C.TEXT)
scribble(fig, 0.08, 0.66, 0.318, color=C.RED_T, lw=3.5)
T(fig, 0.065, 0.225, f"misma presentación: {R['art1_despues']:.0f}%", 56, bold=True)
T(fig, 0.065, 0.135, delta(R["art1_despues"] - R["art1_antes"], 0), 64, bold=True, color=C.RED_T)
hand(fig, 0.48, 0.135, "no era precio,\nera tamaño", 44, color=C.GOLD)
grab(fig, 3000, "carrusel_03_almendras.png")

# ----------------------------------------------------------------------------- 5. lo que sobrevive
CORTO = {("Tortilla de Maíz", "Tortillerías"): "Tortilla (tortillería)", ("Refresco", "Coca Cola. Zero"): "Coca-Cola Zero 600 ml",
         ("Refresco", "Fresca"): "Fresca 3 L", ("Cerveza", "Tecate"): "Tecate 12 latas",
         ("Alimentos Preparados", "Maruchan"): "Sopa Maruchan", ("Lechuga", "S/M"): "Lechuga romana",
         ("Nopal", "S/M"): "Nopal", ("Limón", "S/M"): "Limón persa"}


def corto(r_):
    return CORTO.get((r_.producto, r_.giro if "Tortiller" in str(r_.giro) else r_.marca), r_.producto)


# Regla: los relevantes con la prueba más fuerte, uno por familia y luego se completa hasta 5.
rel = SOB[SOB.relevante].sort_values("p_valor")
pick = rel.drop_duplicates("familia")
pick = pd.concat([pick, rel.drop(pick.index)]).head(5).sort_values("brecha_pct", ascending=False)
fig = new()
title(fig, "4. Lo que sí sobrevive")
T(fig, 0.065, 0.80, f"{R['n_relevantes']:.0f} de {R['n_articulos']:,.0f} artículos con\ndiferencia real entre municipios", 40,
  color=C.TEXT2, va="top", linespacing=1.25)
for k, r_ in enumerate(pick.itertuples()):
    y = 0.60 - k * 0.095
    if k % 2 == 0:
        fig.patches.append(plt.Rectangle((0.04, y - 0.042), 0.92, 0.084, transform=fig.transFigure, color=C.ZEBRA, zorder=0))
    T(fig, 0.07, y, corto(r_), 44, bold=True)
    T(fig, 0.93, y, f"▲ {r_.brecha_pct:.0f}%", 60, bold=True, color=C.GREEN_T, ha="right")
hand(fig, 0.065, 0.10, "aquí la misma cadena\ncobra distinto por plaza", 46, color=C.GOLD)
grab(fig, 3000, "carrusel_04_sobrevive.png")

# ----------------------------------------------------------------------------- 6. cierre
fig = new()
T(fig, 0.065, 0.83, "Una diferencia de precio\nes una pregunta,", 66, bold=True, va="top", linespacing=1.15)
T(fig, 0.065, 0.695, "no una oportunidad.", 66, bold=True, color=C.GOLD, va="top")
scribble(fig, 0.065, 0.85, 0.625)
hand(fig, 0.075, 0.45, "antes de decidir, faltan:", 48, color=C.TEXT2, rot=0)
hand(fig, 0.11, 0.37, "costos · márgenes · volumen", 56, color=C.TEXT, rot=-1)
T(fig, 0.065, 0.19, "Ernesto Roldán | Business Intelligence & Analytics", 32, bold=True, color=C.TEXT)
T(fig, 0.065, 0.145, "Python · Plotly", 24, color=C.TEXT2, small_ok=True)
T(fig, 0.065, 0.075, "Fuente: PROFECO, Quién es Quién en los Precios,\n16-31 ago 2026", 28, color=C.MUTED, linespacing=1.25)
grab(fig, 4000, "carrusel_05_cierre.png")

# ----------------------------------------------------------------------------- exportar
total = sum(ms for _, ms in frames) / 1000
assert total <= 20, total
gif = OUT / "historia_embudo.gif"
pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f, _ in frames]
pal[0].save(gif, save_all=True, append_images=pal[1:], duration=[ms for _, ms in frames], loop=0, optimize=True, disposal=1)
mb = gif.stat().st_size / 1e6
print(f"{gif.name}: {len(frames)} cuadros, {total:.1f} s, {mb:.2f} MB")
print(f"cifras: {R['paso_ingenua']:.1f}% → {R['validada']:.1f}% · >30%: {P30_ING:.1f}% → {P30_VAL:.1f}% · "
      f"{R['n_sobreviven']:.0f} pasan la prueba, {R['n_relevantes']:.0f} relevantes de {R['n_articulos']:,.0f}")
print("cinco que sobreviven:", "; ".join(f"{corto(r_)} {r_.brecha_pct:.0f}%" for r_ in pick.itertuples()))
