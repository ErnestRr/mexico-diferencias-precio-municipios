# Copiado de _profeco_core/src/charts.py por publicar.py; no editar aquí.
"""Plantilla de gráficas de la serie PROFECO (fuente: mexico-mismo-producto-precio, el análisis de referencia,
que a su vez parte de mexico-costo-canasta/src/charts.py).

Identidad visual:
- fondo azul pizarra #161b24; título alineado a la izquierda con barra de acento verde azulado; el título dice
  el hallazgo y el subtítulo dice qué se mide;
- color por signo literal: verde = valor positivo (▲, más caro que la referencia); rojo = negativo (▼, más
  barato); ▲ / ▼ siempre acompañan al color; dorado = referencia (mediana, umbral, valor principal);
- cifras clave en negrita y color dentro del texto (`_finish` con tramos n, b, g, r);
- recuadro «¿Cómo leer?» cuando la figura lo necesita; cuadrícula visible (`_frame`);
- matrices como tabla: bordes de celda, encabezados centrados con fondo de color (`_heat`, `_col_header`,
  `_head_cell`, `_row_header`, `_colorbar`);
- pie «Fuente: elaboración propia con datos de …»; en outputs/social/ además la firma (`_firma`).

Formatos: gráfica grande en outputs/charts/ (ancho 1600–2200 px, alto según filas) y versiones para
publicar en outputs/social/ con `social_canvas("horizontal")` (1280×720) y `social_canvas("vertical")` (1080×1350),
rediseñadas para su tamaño, nunca comprimidas.
"""
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator
from matplotlib.transforms import blended_transform_factory

FIG, PANEL, BOX = "#161b24", "#161b24", "#1f2633"
AXIS, GRID = "#5b6578", "#283041"
TEXT, TEXT2, MUTED, INK = "#f1f3f7", "#c3c9d4", "#8a93a3", "#0f141c"  # INK: texto sobre marcas de color
TEAL, CORAL, NEUTRAL = "#1fa596", "#e5683f", "#7d8697"
SLATE, SAND, GOLD = "#8592ad", "#a8946c", "#d6b25e"
OCEAN, LAND, NODATA = "#0e1726", "#000000", "#000000"
# Secuencial de una familia (azul noche -> verde azulado -> menta), luminosidad creciente.
SEQ = LinearSegmentedColormap.from_list(
    "noche_menta", ["#1b2a3a", "#1d4a5a", "#1f6f75", "#2a968a", "#5dbd9c", "#a9dfbf", "#eaf7e4"])
DIVERGING = LinearSegmentedColormap.from_list("verde_coral", [TEAL, "#2a313d", CORAL])
HALO = [pe.withStroke(linewidth=2.2, foreground=FIG)]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "figure.facecolor": FIG, "axes.facecolor": PANEL, "savefig.facecolor": FIG,
    "axes.edgecolor": AXIS, "axes.labelcolor": TEXT, "xtick.color": TEXT, "ytick.color": TEXT,
    "text.color": TEXT, "grid.color": GRID, "grid.linewidth": 0.4, "axes.axisbelow": True,
    "xtick.labelcolor": TEXT, "ytick.labelcolor": TEXT,
})




def frame(ax, grid="both", box=False):
    """Ejes abiertos (izquierdo e inferior) finos y cuadrícula tenue; box=True cierra el marco."""
    for side, s in ax.spines.items():
        s.set_visible(box or side in ("left", "bottom"))
        s.set_color(AXIS)
        s.set_linewidth(0.6)
    if grid:
        ax.grid(True, axis=grid, color=GRID, lw=0.4)
    ax.tick_params(colors=TEXT, length=2.5, width=0.5, labelsize=9, pad=4)


DPI = 200
W, H = 1280, 720
GREEN, RED = "#1fa874", "#ea5148"          # marcas
GREEN_T, RED_T = "#3fcf95", "#ff6b5f"      # texto: un paso más claro para leerse sobre el fondo
ZEBRA = "#1b212c"
DIV = LinearSegmentedColormap.from_list("rojo_verde", [RED, "#2a313d", GREEN])
DIV.set_bad(ZEBRA)
SRC = "Fuente: elaboración propia con datos de PROFECO, Quién es Quién en los Precios (16–31 ago 2026)"
CHAIN = {"H.e.b.": "HEB", "Wal-mart": "Walmart", "Wal-mart Express": "Walmart Express",
         "Bodega Aurrera": "Bodega Aurrerá",
         "Bodega Aurrera Express": "Bodega Aurrerá Express"}


# --------------------------------------------------------------------------- texto
def n(t):
    return (t, False, None)


def b(t):
    return (t, True, None)


def g(t):
    return (t, True, GREEN_T)


def r(t):
    return (t, True, RED_T)


def minus(s):
    return s.replace("-", "−")


def dpct(v, dec=1):
    """Delta en %: ▲ verde si es positivo, ▼ rojo si es negativo."""
    if round(v, dec) == 0:
        return b(f"= {0:.{dec}f}%")
    return (g if v > 0 else r)(minus(f"{'▲' if v > 0 else '▼'} {v:+.{dec}f}%"))


def pct_axis(v, _=None):
    return "mediana" if abs(v) < 1e-9 else minus(f"{v:+.0f}%")


def chain(c):
    return CHAIN.get(c, c)


_DUP = set()


def register_cities(ids):
    """Nombres de municipio repetidos en varios estados: se les agrega el estado."""
    names = pd.Series([i.split(" | ")[1] for i in pd.unique(pd.Series(list(ids)))])
    _DUP.clear()
    _DUP.update(names[names.duplicated()].tolist())


def city(a):
    est, mun = a.split(" | ") if " | " in a else ("", a)
    return f"{mun} ({est})" if mun in _DUP else mun


def _parts(line):
    if isinstance(line, str):
        return [(line, False, None)]
    if isinstance(line, tuple):
        line = [line]
    return [(p[0], p[1], p[2] if len(p) > 2 else None) if not isinstance(p, str) else (p, False, None)
            for p in line]


def _rich(target, x, y, parts, size, ha="left", va="top", color=TEXT, zorder=5):
    """Una línea con tramos normales, en negrita y de color; target = figura o ejes."""
    is_ax = isinstance(target, Axes)
    fig = target.figure if is_ax else target
    tr = target.transAxes if is_ax else fig.transFigure
    renderer = fig.canvas.get_renderer()
    objs = [target.text(0, y, t, transform=tr, fontsize=size, fontweight="bold" if bo else "normal",
                        color=c or color, va=va, ha="left", parse_math=False, zorder=zorder)
            for t, bo, c in _parts(parts)]
    widths = [o.get_window_extent(renderer).width / target.bbox.width for o in objs]
    start = {"center": x - sum(widths) / 2, "right": x - sum(widths)}.get(ha, x)
    for o, w in zip(objs, widths):
        o.set_x(start)
        start += w
    return sum(widths)


def _box(target, x, y, lines, anchor="ul", size=7, zorder=20):
    """Recuadro de relleno suave con líneas enriquecidas; anchor: ul/ur/ll/lr."""
    is_ax = isinstance(target, Axes)
    fig = target.figure if is_ax else target
    tr = target.transAxes if is_ax else fig.transFigure
    renderer = fig.canvas.get_renderer()
    px = size * fig.dpi / 72
    line_h, pad = px * 1.45, px * 0.8
    rows = []
    for line in lines:
        objs = [target.text(0, 0, t, transform=tr, fontsize=size, fontweight="bold" if bo else "normal",
                            color=c or TEXT, va="top", ha="left", zorder=zorder + 1, parse_math=False)
                for t, bo, c in _parts(line)]
        rows.append((objs, [o.get_window_extent(renderer).width for o in objs]))
    w = max(sum(ws) for _, ws in rows) + 2 * pad
    h = len(rows) * line_h + 1.3 * pad
    ox, oy = tr.transform((x, y))
    left = ox - (w if anchor[1] == "r" else 0)
    top = oy + (h if anchor[0] == "l" else 0)
    inv = tr.inverted()
    for i, (objs, ws) in enumerate(rows):
        cur = left + pad
        for o, wi in zip(objs, ws):
            o.set_position(inv.transform((cur, top - pad - i * line_h)))
            cur += wi
    (x0, y0), (x1, y1) = inv.transform((left, top - h)), inv.transform((left + w, top))
    rect = Rectangle((x0, y0), x1 - x0, y1 - y0, transform=tr, facecolor=BOX, edgecolor=GRID, lw=0.5,
                     zorder=zorder, clip_on=False)
    (target.add_patch if is_ax else fig.add_artist)(rect)


def _header(fig, lines, subtitle=None, size=10.5, top=0.965, left=0.022):
    lines = [lines] if isinstance(lines[0], (tuple, str)) else lines
    y = top
    step = size * 1.45 / 72 / fig.get_figheight()
    x = left + 14 / fig.bbox.width
    for parts in lines:
        _rich(fig, x, y, parts, size)
        y -= step
    bottom = y + step * 0.18
    if subtitle:
        _rich(fig, x, y - 0.002, subtitle, size * 0.64, color=TEXT2)
        bottom = y - size * 0.64 * 1.3 / 72 / fig.get_figheight()
    fig.add_artist(Rectangle((left, bottom), 5 / fig.bbox.width, top - bottom, transform=fig.transFigure,
                             color=TEAL, lw=0))


def _footer(fig, parts, size=6.2, y=None):
    y = 10 / fig.bbox.height if y is None else y
    _rich(fig, 0.022, y, parts, size, va="bottom", color=MUTED)


def _finish(fig, title, subtitle, source, size=10.5, foot=6.2, top=None):
    _header(fig, title, subtitle, size=size, top=top or 1 - 22 / fig.bbox.height)
    _footer(fig, source, foot)


SCALE = 1.2  # texto 20 % más grande respecto a la imagen (se conserva el tamaño en píxeles)


def _canvas(w, h, scale=SCALE):
    dpi = DPI * scale
    return plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)


GRID_STRONG = "#3d485c"
CELL_LINE = "#56627a"   # bordes de celda en matrices (como una tabla)
HEAD_BG = "#b5533a"     # fondo del encabezado de columnas


def _frame(ax, grid="both", size=7):
    """Marco completo y cuadrícula sutil pero visible (más marcada que la plantilla base)."""
    frame(ax, grid=None, box=True)
    if grid:
        ax.grid(True, axis=grid, color=GRID_STRONG, lw=0.75)
    ax.tick_params(labelsize=size)


def _save(fig, path, svg=False):
    fig.savefig(path, dpi=fig.dpi)
    if svg:
        fig.savefig(str(path)[:-4] + ".svg", dpi=fig.dpi)
    return fig



SRC_SM = SRC + ". Supermercados y autoservicio; productos de marca."
GROUP_COLOR = {"Bebidas": "#5b8fd6", "Pan y galletas": SAND, "Lácteos y refrigerados": "#9fb3c8",
               "Abarrotes": SLATE, "Limpieza": "#7fa7a0", "Higiene y cuidado personal": "#b89ac9"}



# --------------------------------------------------------------------------- matrices (del proyecto anterior)
def _heat(ax, m, vmax, fmt, size):
    im = ax.imshow(np.ma.masked_invalid(m), cmap=DIV, norm=TwoSlopeNorm(0, -vmax, vmax), aspect="auto")
    for (i, j), v in np.ndenumerate(m):
        if not np.isnan(v):
            ax.text(j, i, fmt(v), ha="center", va="center", fontsize=size,
                    color=TEXT if abs(v) > vmax * 0.45 else TEXT2, fontweight="bold" if abs(v) > vmax * 0.45 else "normal")
    ax.set_xticks(np.arange(-0.5, m.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, m.shape[0]), minor=True)
    ax.grid(True, which="minor", color=CELL_LINE, lw=1.0)
    ax.grid(False, which="major")
    ax.tick_params(which="both", length=0)
    for sp in ax.spines.values():
        sp.set_color(CELL_LINE)
        sp.set_linewidth(1.2)
    return im


def _col_header(fig, ax, labels, band_px, size=7.6, bold_first=0):
    """Encabezado de columnas como en una tabla: banda de color, texto vertical centrado en cada celda."""
    pos = ax.get_position()
    h = fig.bbox.height
    hax = fig.add_axes([pos.x0, pos.y1, pos.width, band_px / h])
    k = len(labels)
    hax.set(xlim=(-0.5, k - 0.5), ylim=(0, 1))
    hax.axis("off")
    for j, lab in enumerate(labels):
        hax.add_patch(Rectangle((j - 0.5, 0), 1, 1, facecolor=HEAD_BG, edgecolor=CELL_LINE, lw=1.0))
        hax.text(j, 0.5, lab, rotation=90, ha="center", va="center", fontsize=size, color=TEXT,
                 fontweight="bold", rotation_mode="anchor")
    ax.set_xticks([])
    return hax


def _head_cell(fig, x0, x1, ax, band_px, text, size=7.6):
    """Celda de encabezado (fondo de color) sobre una columna, en fracción de figura."""
    pos = ax.get_position()
    y0, hb = pos.y1, band_px / fig.bbox.height
    fig.add_artist(Rectangle((x0, y0), x1 - x0, hb, transform=fig.transFigure, facecolor=HEAD_BG,
                             edgecolor=CELL_LINE, lw=1.0))
    fig.text((x0 + x1) / 2, y0 + hb / 2, text, ha="center", va="center", fontsize=size, fontweight="bold",
             color=TEXT, linespacing=1.3)


def _row_header(fig, ax, labels, width_px, size=7.2):
    """Columna de nombres como en una tabla: celdas con borde y texto centrado."""
    pos = ax.get_position()
    w = fig.bbox.width
    rax = fig.add_axes([pos.x0 - width_px / w, pos.y0, width_px / w, pos.height])
    k = len(labels)
    rax.set(xlim=(0, 1), ylim=(k - 0.5, -0.5))
    rax.axis("off")
    for i, lab in enumerate(labels):
        rax.add_patch(Rectangle((0, i - 0.5), 1, 1, facecolor=BOX if i % 2 else ZEBRA, edgecolor=CELL_LINE, lw=1.0))
        rax.text(0.5, i, lab, ha="center", va="center", fontsize=size, color=TEXT)
    ax.set_yticks([])
    return rax


def _colorbar(fig, im, rect, label, fmt):
    cax = fig.add_axes(rect)
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend="both")
    cb.outline.set_edgecolor(AXIS)
    cb.outline.set_linewidth(0.5)
    cb.ax.tick_params(colors=TEXT, length=2.5, width=0.5, labelsize=7)
    cb.ax.xaxis.set_major_formatter(fmt)
    cb.ax.set_title(label, fontsize=7.4, color=TEXT2, loc="left", pad=5)




# --------------------------------------------------------------------------- comunes
def _sign_color(v, tol=0.5):
    return np.where(v < -tol, RED, np.where(v > tol, GREEN, NEUTRAL))


def money(v, _=None):
    return f"${v:,.2f}" if v < 100 and round(v) != v else f"${v:,.0f}"


def money_tex(v):
    """Igual que money, para un ax.text con dos signos $ (matplotlib los leería como fórmula).
    No usar en _finish, _box ni _rich: ahí no se interpretan fórmulas y se vería una diagonal antes del signo."""
    return money(v).replace("$", r"\$")


def _wrap(txt, width):
    lines, cur = [], ""
    for wd in txt.split():
        if cur and len(cur) + len(wd) + 1 > width:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    return "\n".join(lines + [cur])


# --------------------------------------------------------------------------- firma y formatos sociales
FIRMA = "Ernesto Roldán | Business Intelligence & Analytics | Inteligencia económica aplicada a pricing y rentabilidad"
SOCIAL = {"horizontal": (1280, 720), "vertical": (1080, 1350)}


def social_canvas(fmt, scale=1.0):
    """Lienzo de tamaño exacto para outputs/social/ (1280×720 o 1080×1350 px)."""
    w, h = SOCIAL[fmt]
    return _canvas(w, h, scale)


def _firma(fig, size=5.6, y=None):
    """Firma a la derecha del pie, en el mismo renglón de la fuente."""
    y = 10 / fig.bbox.height if y is None else y
    fig.text(0.985, y, FIRMA, ha="right", va="bottom", fontsize=size, color=TEXT2, fontweight="bold")


def finish_social(fig, title, subtitle, source, size=11, foot=5.6):
    """Encabezado, fuente (arriba de la firma) y firma para una gráfica de outputs/social/."""
    _header(fig, title, subtitle, size=size, top=1 - 22 / fig.bbox.height)
    _footer(fig, source, foot, y=10 / fig.bbox.height + foot * 1.6 * fig.dpi / 72 / fig.bbox.height)
    _firma(fig, foot)
