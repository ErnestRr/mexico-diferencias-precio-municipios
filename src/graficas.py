"""Gráficas del embudo de comparabilidad con la plantilla del núcleo (charts.py).

Convenciones: ▼ rojo = la diferencia baja (cambio negativo); ▲ verde = sube; dorado = referencia (lo que daría el
azar); gris = no distinta de la referencia. Las brechas se leen como «cuánto más cuesta en el municipio caro típico
que en el barato típico».
"""
import textwrap

import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.ticker import MultipleLocator, FixedLocator, NullFormatter
from matplotlib.transforms import blended_transform_factory

import charts as C
from charts import n, b, g, r, minus, _box, _finish, _canvas, _frame, _save

SRC_E = C.SRC + ". Sin medicamentos; tiendas monitoreadas por PROFECO."
BAR = C.SLATE
ING = C.SAND
SUB = {"ingenua": "nombre del producto y promedio simple", "presentacion": "mismo tamaño y unidad (kg, litro, pieza)",
       "marca": "misma marca y variedad", "giro": "súper con súper, mercado con mercado",
       "tiendas": "precio de tienda y 3 o más por municipio", "periodo": "ajuste por el día de captura",
       "extremos": "fuera de 0.5×–2× de su propia cadena"}


def _chg(v, dec=1):
    """Cambio en puntos: ▼ rojo si baja, ▲ verde si sube, = si casi no cambia."""
    if abs(v) < 0.05:
        return "= 0.0 pp", C.TEXT2
    return minus(f"{'▲' if v > 0 else '▼'} {v:+.{dec}f} pp"), (C.GREEN_T if v > 0 else C.RED_T)


def _zebra(fig, ax, k, x0=0.015, x1=0.97):
    tr = blended_transform_factory(fig.transFigure, ax.transData)
    for i in range(k):
        if i % 2 == 0:
            ax.add_patch(Rectangle((x0, i - 0.5), x1, 1, transform=tr, color=C.ZEBRA, lw=0, zorder=0))
    return tr


# --------------------------------------------------------------------------- 01 principal: embudo
def embudo(res, v, path, svg=True):
    k = len(res)
    fig = _canvas(2000, 1300)
    L = 0.30
    ax = fig.add_axes([L, 0.12, 0.50, 0.545])
    ax.patch.set_alpha(0)
    tr = _zebra(fig, ax, k)
    xmax = max(30, np.ceil(res.ic90_sup.max() / 5) * 5 + 5)
    for i, rw in enumerate(res.itertuples()):
        last, first = i == k - 1, i == 0
        col = ING if first else BAR
        ax.barh(i, rw.brecha_mediana, height=0.62, color=col, alpha=1 if (first or last) else 0.75,
                edgecolor=C.TEXT if last else "none", lw=1.4 if last else 0, zorder=2)
        if first or last:
            ax.hlines(i, rw.ic90_inf, rw.ic90_sup, color=C.TEXT, lw=2.2, zorder=4)
            ax.vlines([rw.ic90_inf, rw.ic90_sup], i - 0.12, i + 0.12, color=C.TEXT, lw=2.2, zorder=4)
        ax.text(L - 0.012, i - 0.12, f"{i}. {rw.nombre}" if i else "0. " + rw.nombre, transform=tr, ha="right", va="center",
                fontsize=8.6, fontweight="bold", color=C.TEXT)
        ax.text(L - 0.012, i + 0.24, SUB.get(rw.paso, ""), transform=tr, ha="right",
                va="center", fontsize=6.4, color=C.TEXT2)
        ax.text(0.815, i - 0.1, f"{rw.brecha_mediana:.1f}%", transform=tr, ha="left", va="center", fontsize=9.6,
                fontweight="bold", color=C.TEXT)
        if first:
            sub, sc = minus(f"IC90 {rw.ic90_inf:.0f}–{rw.ic90_sup:.0f}%"), C.TEXT2
        elif last:
            sub, sc = minus(f"IC90 {rw.ic90_inf:.1f}–{rw.ic90_sup:.1f}%"), C.TEXT2
        else:
            sub, sc = _chg(rw.cambio_pp)
        ax.text(0.815, i + 0.27, sub, transform=tr, ha="left", va="center", fontsize=6.8, fontweight="bold", color=sc)
    az = v["azar"]
    ax.axvline(az, color=C.GOLD, lw=1.6, ls=(0, (4, 3)), zorder=3)
    ax.text(az, -0.62, minus(f"Azar: {az:.1f}%"), ha="center", va="bottom", fontsize=7.2, fontweight="bold", color=C.GOLD)
    ax.set(xlim=(0, xmax), ylim=(k - 0.5, -0.5), yticks=[])
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    _frame(ax, grid="x", size=7.2)
    ax.set_xlabel("Cuánto más cuesta el producto típico en el municipio caro típico que en el barato típico (brecha P90/P10)",
                  fontsize=7.2, labelpad=5)
    _box(fig, 0.03, 0.815, [[b("¿Cómo leer?  "), n("Cada barra es la diferencia que queda después de esa validación, en los mismos "
                                                    f"{v['productos_universo']:.0f} productos.")],
                            [n("Línea dorada: la diferencia que daría repartir al azar las mismas tiendas entre municipios. "
                               "Lo que queda cerca de ella no es del municipio.")],
                            [r("▼ rojo"), n(": cuánto baja la diferencia en ese paso.  Barra blanca: rango probable (IC 90%).")]],
         "ul", size=7.3)
    _finish(fig, [[n("Al comparar lo mismo, la diferencia típica de precio entre municipios baja de "), b(f"{v['paso_ingenua']:.0f}%"),
                   n(" a "), b(f"{v['validada']:.0f}%")],
                  [n("y queda casi igual a la que daría el azar ("), (f"{v['azar']:.0f}%", True, C.GOLD),
                   n("): desaparece "), r(f"▼ {v['desaparece_pct']:.0f}%"), n(" de la diferencia ingenua")]],
            f"Brecha P90/P10 entre municipios, mediana de {v['productos_universo']:.0f} nombres de producto; cada paso exige lo anterior; "
            "IC90 por bootstrap de municipios",
            [n(SRC_E)], size=12.5, foot=6.0, top=1 - 26 / 1300)
    return _save(fig, path, svg)


def embudo_social(res, v, fmt, path):
    fig = C.social_canvas(fmt)
    W, H = C.SOCIAL[fmt]
    vertical = H > W
    top = (390 if vertical else 215) / H
    bot = (175 if vertical else 120) / H
    L = 0.36 if vertical else 0.30
    ax = fig.add_axes([L, bot, 0.84 - L, 1 - top - bot])
    k = len(res)
    for i, rw in enumerate(res.itertuples()):
        last, first = i == k - 1, i == 0
        ax.barh(i, rw.brecha_mediana, height=0.62, color=ING if first else BAR, alpha=1 if (first or last) else 0.75,
                edgecolor=C.TEXT if last else "none", lw=1.2 if last else 0)
        ax.text(-0.02, i, rw.nombre, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6.8,
                fontweight="bold")
        ax.text(rw.brecha_mediana + 0.5, i, f"{rw.brecha_mediana:.0f}%", ha="left", va="center", fontsize=7,
                fontweight="bold", color=C.TEXT)
    ax.axvline(v["azar"], color=C.GOLD, lw=1.4, ls=(0, (4, 3)))
    ax.text(v["azar"], -0.7, f"Azar: {v['azar']:.0f}%", ha="center", va="bottom", fontsize=6.4, fontweight="bold", color=C.GOLD)
    ax.set(xlim=(0, 30), ylim=(k - 0.5, -0.5), yticks=[])
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    _frame(ax, grid="x", size=6.2)
    ax.set_xlabel("Diferencia entre el municipio caro típico y el barato típico", fontsize=6.2)
    if vertical:
        title = [[n("Una diferencia de precio entre")], [n("ciudades no es una oportunidad:")],
                 [n("al comparar lo mismo baja de "), b(f"{v['paso_ingenua']:.0f}%")], [n("a "), b(f"{v['validada']:.0f}%"),
                 n(", casi lo mismo que el azar")]]
        sub = f"Mediana de {v['productos_universo']:.0f} productos; tiendas monitoreadas por PROFECO, 16–31 ago 2026"
    else:
        title = [[n("Al comparar lo mismo, la diferencia de precio entre municipios baja de "), b(f"{v['paso_ingenua']:.0f}%")],
                 [n("a "), b(f"{v['validada']:.0f}%"), n(", casi igual a la que daría el azar ("), (f"{v['azar']:.0f}%", True, C.GOLD), n(")")]]
        sub = (f"Brecha P90/P10 entre municipios, mediana de {v['productos_universo']:.0f} nombres de producto (sin medicamentos); "
               "16–31 ago 2026")
    C.finish_social(fig, title, sub, [n("Fuente: elaboración propia con datos de PROFECO, Quién es Quién en los Precios.")],
                    size=12.5 if vertical else 11, foot=5.4)
    fig.savefig(path, dpi=fig.dpi)
    return fig


# --------------------------------------------------------------------------- 02 distribución
def distribucion(prod, v, path):
    x = prod.dropna(subset=["ingenua", "extremos"])
    bins = np.r_[0, 2.5, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 200, 1000]
    lab = ["0–2.5", "2.5–5", "5–7.5", "7.5–10", "10–15", "15–20", "20–25", "25–30", "30–40", "40–50", "50–75", "75–100",
           "100–200", "200+"]
    hi = pd.cut(x.ingenua.clip(upper=999), bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
    hv = pd.cut(x.extremos.clip(upper=999), bins, labels=lab, right=False).value_counts(normalize=True).reindex(lab) * 100
    fig = _canvas(2000, 1200)
    ax = fig.add_axes([0.07, 0.15, 0.88, 0.5])
    pos = np.arange(len(lab))
    ax.bar(pos - 0.2, hi, width=0.38, color=ING, label="Comparación ingenua", zorder=2)
    ax.bar(pos + 0.2, hv, width=0.38, color=BAR, label="Validada", zorder=2, edgecolor=C.TEXT, lw=0.6)
    for p_, a_, c_ in zip(pos, hi, hv):
        if a_ >= 1:
            ax.text(p_ - 0.2, a_ + 0.4, f"{a_:.0f}", ha="center", va="bottom", fontsize=6, color=C.TEXT2)
        if c_ >= 1:
            ax.text(p_ + 0.2, c_ + 0.4, f"{c_:.0f}", ha="center", va="bottom", fontsize=6, color=C.TEXT)
    ax.set_xticks(pos, [l_ + "%" for l_ in lab], fontsize=6.6)
    ax.set_ylabel("% de los productos", fontsize=7.2)
    ax.set_ylim(0, max(hi.max(), hv.max()) * 1.18)
    _frame(ax, grid="y", size=6.8)
    ax.set_xlabel("Cuánto más cuesta en el municipio caro típico que en el barato típico", fontsize=7.2, labelpad=5)
    leg = ax.legend(loc="upper right", fontsize=7, frameon=True)
    leg.get_frame().set_facecolor(C.BOX)
    leg.get_frame().set_edgecolor(C.GRID)
    for t in leg.get_texts():
        t.set_color(C.TEXT)
    p30i, p30v = (x.ingenua > 30).mean() * 100, (x.extremos > 30).mean() * 100
    _box(fig, 0.07, 0.80, [[b("¿Cómo leer?  "), n("Cada barra: qué parte de los productos tiene una diferencia entre municipios en ese rango.")],
                           [n("Ingenua: por nombre y promedio. Validada: mismo artículo, 3 tiendas o más por municipio, ajustada por día y sin errores.")],
                           [n("Con diferencias de más de 30%: "), b(f"{p30i:.0f}%"), n(" de los productos a lo bruto y "), b(f"{p30v:.0f}%"),
                            n(" validados.")]], "ul", size=7.3)
    _finish(fig, [[n("A lo bruto, "), b(f"{p30i:.0f}%"), n(" de los productos parece costar más de 30% más en otro municipio;")],
                  [n("al comparar el mismo artículo con 3 tiendas o más, solo "), b(f"{p30v:.0f}%")]],
            f"Distribución de la brecha P90/P10 entre municipios en {len(x)} nombres de producto; comparación ingenua contra validada",
            [n(SRC_E)], size=12.5, foot=6.0, top=1 - 26 / 1200)
    return _save(fig, path)


# --------------------------------------------------------------------------- 03 artefactos
def artefactos(casos, path):
    k = len(casos)
    fig = _canvas(2200, 1650)
    L = 0.22
    ax = fig.add_axes([L, 0.09, 0.38, 0.69])
    ax.patch.set_alpha(0)
    tr = _zebra(fig, ax, k)
    for i, c in enumerate(casos.itertuples()):
        ax.text(L - 0.012, i - 0.14, c.tipo, transform=tr, ha="right", va="center", fontsize=8.6, fontweight="bold", color=C.TEXT)
        ax.text(L - 0.012, i + 0.2, f"«{c.producto[0] + c.producto[1:].lower()}»", transform=tr, ha="right", va="center", fontsize=7, color=C.TEXT2)
        a0, a1 = c.antes, c.despues
        ax.add_patch(FancyArrowPatch((a0, i), (a1, i), arrowstyle="-|>", mutation_scale=14, color=C.RED, lw=2.2, zorder=3,
                                     shrinkA=7, shrinkB=7))
        ax.scatter([a0], [i], s=120, color=ING, edgecolor=C.TEXT, lw=0.8, zorder=4)
        ax.scatter([a1], [i], s=120, color=BAR, edgecolor=C.TEXT, lw=0.8, zorder=4)
        ax.text(a0 * 1.25, i, f"{a0:.0f}%", ha="left", va="center", fontsize=7.4, fontweight="bold", color=C.TEXT, path_effects=C.HALO)
        ax.text(a1 / 1.25, i, f"{a1:.0f}%", ha="right", va="center", fontsize=7.4, fontweight="bold", color=C.TEXT, path_effects=C.HALO)
        lines = textwrap.wrap(c.explicacion, 72)
        for j, ln in enumerate(lines[:4]):
            ax.text(0.625, i - 0.36 + j * 0.17, ln, transform=tr, ha="left", va="center", fontsize=6.4, color=C.TEXT2, parse_math=False)
        ax.text(0.625, i + 0.36, minus(f"Nombre completo: {c.ingenua:.0f}% a lo bruto → {c.validada:.0f}% validado"), transform=tr,
                ha="left", va="center", fontsize=6.2, fontweight="bold", color=C.TEXT)
    ax.set_xscale("log")
    ax.set(xlim=(2, 1500), ylim=(k - 0.5, -0.5), yticks=[])
    ax.xaxis.set_major_locator(FixedLocator([2, 5, 10, 20, 50, 100, 200, 500, 1000]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:g}%")
    _frame(ax, grid="x", size=7)
    ax.set_xlabel("Diferencia entre el municipio caro y el barato típicos, antes y después de la validación (escala logarítmica)", fontsize=6.8, labelpad=5)
    _box(fig, 0.03, 0.875, [[b("¿Cómo leer?  "), ("●", True, ING), n(" diferencia antes de la validación; "), ("●", True, BAR),
                             n(" después; "), r("▼"), n(" cuánto baja. A la derecha, qué la producía.")],
                            [n("Casos elegidos con una regla: en cada paso, el producto cuya diferencia más baja con esa validación.")]],
         "ul", size=7.3)
    _finish(fig, [[n("Cómo nace una diferencia falsa: otra presentación, otra marca, otro giro, una sola tienda o una captura errónea")],
                  [n("pueden hacer que un producto parezca "), b(f"{casos.antes.max():.0f}%"), n(" más caro en otro municipio")]],
            "Cinco casos donde la diferencia ingenua entre municipios era un artefacto; brecha P90/P10 antes y después de cada validación",
            [n(SRC_E)], size=12.5, foot=6.0, top=1 - 26 / 1650)
    return _save(fig, path)


# --------------------------------------------------------------------------- 04 sobrevivientes
def sobrevivientes(sob, casos, v, path, k=12):
    s = pd.concat([casos, sob]).drop_duplicates(["producto", "pres_key", "presentacion", "marca", "giro"]).head(k).reset_index(drop=True)
    fig = _canvas(2000, 1500)
    L = 0.33
    ax = fig.add_axes([L, 0.10, 0.45, 0.66])
    ax.patch.set_alpha(0)
    tr = _zebra(fig, ax, len(s))
    import embudo as M
    for i, c in enumerate(s.itertuples()):
        solid = bool(c.relevante)
        col = C.GREEN if solid else C.NEUTRAL
        ax.text(L - 0.012, i - 0.13, textwrap.shorten(c.etiqueta, 40, placeholder="…"), transform=tr, ha="right", va="center",
                fontsize=8, fontweight="bold", color=C.TEXT)
        ax.text(L - 0.012, i + 0.24, f"{M.giro_corto(c.giro)} · {int(c.municipios)} municipios", transform=tr, ha="right",
                va="center", fontsize=6.2, color=C.TEXT2)
        ax.hlines(i, c.ic90_inf, c.ic90_sup, color=col, lw=8, alpha=0.45, zorder=2)
        ax.scatter([c.brecha_pct], [i], s=120, marker="D", color=col, edgecolor=C.TEXT, lw=0.8, zorder=4)
        ax.plot([c.azar_mediana, c.azar_mediana], [i - 0.3, i + 0.3], color=C.GOLD, lw=2, zorder=3)
        t, tc = (f"▲ {c.brecha_pct:.0f}%", C.GREEN_T) if solid else (f"{c.brecha_pct:.0f}%", C.TEXT2)
        ax.text(0.8, i - 0.12, t, transform=tr, ha="left", va="center", fontsize=8.4, fontweight="bold", color=tc)
        ax.text(0.8, i + 0.24, minus(f"IC90 {c.ic90_inf:.0f}–{c.ic90_sup:.0f}% · {C.money(c.precio_barato)} a {C.money(c.precio_caro)}"),
                transform=tr, ha="left", va="center", fontsize=6.1, color=C.TEXT2, parse_math=False)
    xmax = np.ceil(s.ic90_sup.max() / 10) * 10 + 5
    ax.set(xlim=(0, xmax), ylim=(len(s) - 0.5, -0.5), yticks=[])
    ax.xaxis.set_major_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0f}%")
    _frame(ax, grid="x", size=7)
    ax.set_xlabel("Cuánto más cuesta en el municipio caro típico que en el barato típico (brecha P90/P10)", fontsize=7, labelpad=5)
    _box(fig, 0.03, 0.855, [[b("¿Cómo leer?  "), ("◆", True, C.GREEN), n(" diferencia entre municipios con su rango probable (IC 90%); "),
                             ("|", True, C.GOLD), n(" lo que daría típicamente el azar con las mismas tiendas.")],
                            [g("▲ verde"), n(": relevante (10% o más y el rango arriba del azar); gris: distinta, pero pequeña o cerca del azar.")],
                            [n("A la derecha, precio en el municipio barato y el caro típicos.")]],
         "ul", size=7.2)
    _finish(fig, [[n("Solo "), b(f"{v['n_sobreviven']:.0f} de {v['n_articulos']:,.0f}"), n(" artículos tienen una diferencia entre municipios que supera la prueba, y")],
                  [b(f"{v['n_relevantes']:.0f}"), n(" son relevantes: sobre todo bebidas de supermercado, frescos y tortilla")]],
            f"Artículos con diferencia entre municipios tras la prueba de rangos con control de falsos positivos (10%); se muestran {len(s)} de {v['n_sobreviven']:.0f}",
            [n(SRC_E)], size=12.5, foot=6.0, top=1 - 26 / 1500)
    return _save(fig, path)


# --------------------------------------------------------------------------- 05 qué falta
def que_falta(falta, v, path):
    fig = _canvas(2200, 1250)
    cols = list(falta.columns)
    cols[1] = "¿En los datos?"
    widths = [0.235, 0.105, 0.255, 0.355]
    x0, y_top, row_h, head_h = 0.025, 0.66, 0.075, 0.06
    xs = np.cumsum([x0] + widths)
    for j, ctext in enumerate(cols):
        fig.patches.append(Rectangle((xs[j], y_top), widths[j], head_h, transform=fig.transFigure, facecolor="#2c4a6e",
                                     edgecolor=C.CELL_LINE, lw=1))
        fig.text(xs[j] + widths[j] / 2, y_top + head_h / 2, ctext, ha="center", va="center", fontsize=7.6, fontweight="bold",
                 color="#ffffff")
    for i, row in enumerate(falta.itertuples(index=False)):
        y = y_top - (i + 1) * row_h
        for j, val in enumerate(row):
            fig.patches.append(Rectangle((xs[j], y), widths[j], row_h, transform=fig.transFigure,
                                         facecolor=C.ZEBRA if i % 2 == 0 else C.BOX, edgecolor=C.CELL_LINE, lw=1))
            if j == 1:
                colr = C.TEXT if val == "No" else C.GOLD
                fig.text(xs[j] + widths[j] / 2, y + row_h / 2, val, ha="center", va="center", fontsize=8.2, fontweight="bold", color=colr)
            else:
                wrap = textwrap.wrap(str(val), int(widths[j] * (150 if j == 0 else 205)))
                fig.text(xs[j] + 0.008, y + row_h / 2, "\n".join(wrap[:2]), ha="left", va="center", fontsize=7 if j == 0 else 6.5,
                         fontweight="bold" if j == 0 else "normal", color=C.TEXT if j == 0 else C.TEXT2, linespacing=1.25)
    _box(fig, 0.025, 0.815, [[b("¿Cómo leer?  "), n("Lo que haría falta para saber si una diferencia de precio es una oportunidad de negocio, y si está en los datos usados.")],
                            [n("No se calcula arbitraje ni rentabilidad. Las fuentes de INEGI son un siguiente paso posible; no se usaron.")]],
         "ul", size=7.3)
    _finish(fig, [[n("Para hablar de oportunidad faltan costos, márgenes y volumen:")],
                  [b(f"{v['falta_no']:.0f} de {len(falta)}"), n(" piezas de información no están en los datos públicos usados")]],
            "Qué se necesitaría para pasar de una diferencia de precio a una decisión comercial; PROFECO solo registra el precio de anaquel",
            [n(SRC_E)], size=12.5, foot=6.0, top=1 - 26 / 1250)
    return _save(fig, path)
