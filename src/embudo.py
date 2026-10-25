"""Embudo de comparabilidad: diferencia de precio entre municipios, de la comparación ingenua a la validada.

Unidad de reporte: el **nombre de producto** de PROFECO (p. ej., «Atún», «Leche»). En cada paso se define qué se
compara dentro de ese nombre (presentación, marca, giro) y cómo se mide el precio de un municipio. La diferencia entre
municipios de una unidad de comparación es la brecha P90/P10 de los precios municipales (cuánto más cuesta en el
municipio caro típico que en el barato típico). La de un nombre de producto es la mediana de sus unidades.
El universo del embudo es fijo: los nombres de producto que llegan al último paso.
"""
import numpy as np
import pandas as pd

SEMILLA = 2026
MIN_MUN = 10          # municipios por unidad: con menos, P10 y P90 son casi el mínimo y el máximo
MIN_TIENDAS = 3       # tiendas por municipio y unidad en el paso 4
MIN_RELEVANTE = 10.0  # brecha validada (%) a partir de la cual una diferencia que sobrevive se considera relevante
ERROR_BAJO, ERROR_ALTO = 0.5, 2.0   # posible error: fuera de 0.5×–2× la mediana de su cadena en la misma unidad
FUERA_PRINCIPAL = ["Medicamentos"]  # sin laboratorio en el dato: el paso «misma marca» no se puede completar
COLS = ["producto", "presentacion", "marca", "categoria", "catalogo", "giro", "cadena_comercial", "estado",
        "municipio", "municipio_id", "establecimiento_id", "sku_id", "fecha", "precio_num", "cantidad_base",
        "unidad_base"]

PASOS = [
    ("ingenua", "Comparación ingenua", "solo el nombre del producto; promedio de todos los registros del municipio"),
    ("presentacion", "Misma presentación", "mismo tamaño y unidad normalizados (kg, litro, pieza)"),
    ("marca", "Mismo artículo", "misma marca y misma descripción de PROFECO (variedad incluida)"),
    ("giro", "Mismo giro", "supermercado contra supermercado, farmacia contra farmacia…"),
    ("tiendas", "3 tiendas o más", "precio de cada tienda (mediana) y al menos 3 tiendas por municipio"),
    ("periodo", "Mismo periodo", "precio ajustado por el día de captura"),
    ("extremos", "Sin errores de captura", "sin precios fuera de 0.5×–2× de su propia cadena"),
]
CLAVES = {"ingenua": ["producto"], "presentacion": ["producto", "pres_key"],
          "marca": ["producto", "pres_key", "presentacion", "marca"],
          "giro": ["producto", "pres_key", "presentacion", "marca", "giro"]}
UNIDAD = CLAVES["giro"]


# --------------------------------------------------------------------------- etiquetas
def presentacion_corta(pres_key, largo=34):
    """«0.6 l» → «600 ml»; «1.0 kg» → «1 kg»; «texto: Pieza. Romana» → «pieza, romana»."""
    s = str(pres_key)
    if s.startswith("texto: "):
        t = s[7:].replace(". ", ", ").strip().rstrip(".").lower()
        return t if len(t) <= largo else t[:largo - 1].rstrip(" ,") + "…"
    try:
        q, u = s.split(" ")
        q = float(q)
    except ValueError:
        return s
    if u == "kg":
        return f"{q * 1000:g} g" if q < 1 else f"{q:g} kg"
    if u == "l":
        return f"{q * 1000:g} ml" if q < 1 else f"{q:g} L"
    if u == "pieza":
        return "pieza" if q == 1 else f"{q:g} piezas"
    return s


def marca_corta(marca):
    m = str(marca)
    return "" if m in ("S/M", "nan", "None", "") else m.replace(". ", " ").replace(".", "")


def giro_corto(giro, plural=False):
    g = str(giro)
    base = {"Supermercado / Tienda de Autoservicio": "supermercado", "Tortillerías": "tortillería", "Mercados": "mercado",
            "Tienda de Conveniencia": "tienda de conveniencia", "Central de Abasto": "central de abasto"}
    for k, val in base.items():
        if k in g or (k.startswith("Tortiller") and "Tortiller" in g):
            if plural:
                return {"supermercado": "supermercados", "tortillería": "tortillerías", "mercado": "mercados",
                        "tienda de conveniencia": "tiendas de conveniencia", "central de abasto": "centrales de abasto"}[val]
            return val
    return g.lower()


def etiqueta(producto, pres_key, marca, presentacion=None):
    """Nombre legible de un artículo: «Refresco Coca Cola Zero (botella 600 ml)», «Lechuga (pieza, romana)».

    Con la descripción literal de PROFECO se ven el empaque y la variedad (p. ej., paquete con 12 latas)."""
    m = marca_corta(marca)
    if presentacion is not None and str(presentacion) not in ("", "nan"):
        return f"{producto} {m}".strip() + f" ({presentacion_corta('texto: ' + str(presentacion), 46)})"
    p = presentacion_corta(pres_key)
    base = f"{producto} {m}".strip()
    return f"{base} ({p})" if str(pres_key).startswith("texto: ") else f"{base} {p}"


# --------------------------------------------------------------------------- datos
def prep(raw):
    """Observaciones con precio > 0, textos como str y clave de presentación normalizada."""
    d = raw.loc[raw.precio_num > 0, [c for c in COLS if c in raw.columns]].copy()
    for c in d.columns:
        if isinstance(d[c].dtype, pd.CategoricalDtype) or d[c].dtype == object:
            d[c] = d[c].astype(str)
    # Presentación: tamaño normalizado con unidades.py (cantidad_base + unidad_base); si no se pudo normalizar,
    # el texto literal (nunca se suponen equivalencias).
    d["pres_key"] = np.where(d.cantidad_base.notna(),
                             d.cantidad_base.round(4).astype(str) + " " + d.unidad_base.astype(str),
                             "texto: " + d.presentacion)
    d["semana"] = np.where(d.fecha <= pd.Timestamp("2026-08-23"), 1, 2)
    return d


def indice_dia(d):
    """Efecto del día de captura: desviación media del log(precio) frente a la media de su cadena y SKU.

    Compara la misma cadena y el mismo artículo en días distintos; como las cadenas cobran casi igual en todas sus
    tiendas, lo que quede es el efecto del día (promociones o cambios de precio en la quincena)."""
    lp = np.log(d.precio_num)
    dev = lp - lp.groupby([d.cadena_comercial, d.sku_id]).transform("mean")
    return dev.groupby(d.fecha).agg(["mean", "size"]).rename(columns={"mean": "efecto_log", "size": "registros"})


def cambio_entre_semanas(d):
    """Misma tienda y mismo SKU en las dos semanas: ¿cambia el precio?"""
    w = d.groupby(["establecimiento_id", "sku_id", "semana"]).precio_num.median().unstack().dropna()
    r = np.log(w[2] / w[1])
    return {"pares": len(w), "tiendas": w.index.get_level_values(0).nunique(),
            "pct_igual": float((r.abs() < 1e-9).mean() * 100),
            "pct_cambio_mayor_5": float((r.abs() > np.log(1.05)).mean() * 100),
            "cambio_mediano_pct": float((np.exp(r.median()) - 1) * 100),
            "cambio_medio_pct": float((np.exp(r.mean()) - 1) * 100)}


# --------------------------------------------------------------------------- precios municipales por paso
def _tiendas(d, precio="precio_num"):
    sp = d.groupby(UNIDAD + ["municipio_id", "establecimiento_id", "cadena_comercial"], observed=True)[precio] \
          .median().rename("precio").reset_index()
    sp["tiendas_mun"] = sp.groupby(UNIDAD + ["municipio_id"]).establecimiento_id.transform("size")
    return sp


def marcar_errores(sp):
    """Posible error de captura: precio fuera de 0.5×–2× la mediana de su propia cadena en la misma unidad.

    Contra la mediana nacional se marcarían como error las diferencias reales entre cadenas o municipios, que es
    justo lo que se mide aquí."""
    sp = sp.copy()
    med = sp.groupby(UNIDAD + ["cadena_comercial"]).precio.transform("median")
    sp["razon_cadena"] = sp.precio / med
    sp["posible_error"] = (sp.razon_cadena < ERROR_BAJO) | (sp.razon_cadena > ERROR_ALTO)
    return sp


def precios_municipales(d, paso, min_tiendas=MIN_TIENDAS, dia=None):
    """Precio de cada unidad de comparación en cada municipio, según el paso del embudo.

    Devuelve columnas: claves de la unidad, municipio_id, precio, tiendas."""
    if paso in CLAVES:
        k = CLAVES[paso]
        g = d.groupby(k + ["municipio_id"], observed=True)
        return g.agg(precio=("precio_num", "mean"), tiendas=("establecimiento_id", "nunique")).reset_index()
    x = d
    if paso in ("periodo", "extremos"):
        dia = indice_dia(d) if dia is None else dia
        x = d.assign(precio_aj=d.precio_num / np.exp(d.fecha.map(dia.efecto_log).fillna(0).to_numpy()))
    sp = _tiendas(x, "precio_aj" if "precio_aj" in x else "precio_num")
    if paso == "extremos":
        sp = marcar_errores(sp)
        sp = sp[~sp.posible_error]
        sp["tiendas_mun"] = sp.groupby(UNIDAD + ["municipio_id"]).establecimiento_id.transform("size")
    sp = sp[sp.tiendas_mun >= min_tiendas]
    return sp.groupby(UNIDAD + ["municipio_id"]).agg(precio=("precio", "median"),
                                                     tiendas=("establecimiento_id", "size")).reset_index()


def brechas(pm, clave, min_mun=MIN_MUN):
    """Brecha P90/P10 entre municipios por unidad de comparación (solo unidades con min_mun municipios o más)."""
    s = pm.groupby(clave).precio.agg(municipios="size", p10=lambda v: v.quantile(.1), p50="median",
                                     p90=lambda v: v.quantile(.9)).reset_index()
    s = s[s.municipios >= min_mun].copy()
    s["brecha_pct"] = (s.p90 / s.p10 - 1) * 100
    return s


def embudo(d, min_tiendas=MIN_TIENDAS, min_mun=MIN_MUN, pasos=None, universo=None):
    """Brecha por nombre de producto en cada paso, sobre un universo fijo.

    Devuelve (resumen por paso, brecha por producto y paso, unidades por paso, precios municipales por paso)."""
    pasos = pasos or [p for p, *_ in PASOS]
    dia = indice_dia(d)
    pm, un = {}, {}
    for p in pasos:
        pm[p] = precios_municipales(d, p, min_tiendas, dia)
        un[p] = brechas(pm[p], CLAVES.get(p, UNIDAD), min_mun)
    if universo is None:
        universo = set(un[pasos[-1]].producto) & set(un[pasos[0]].producto)
    prod = pd.DataFrame({p: un[p][un[p].producto.isin(universo)].groupby("producto").brecha_pct.median()
                         for p in pasos})
    res = pd.DataFrame([{"paso": p, "unidades": int(un[p].producto.isin(universo).sum()), "productos": int(prod[p].notna().sum()),
                         "brecha_mediana": prod[p].median(), "brecha_promedio": prod[p].mean()} for p in pasos])
    return res, prod, un, pm


# --------------------------------------------------------------------------- incertidumbre
def _matriz(pm, clave):
    m = pm.assign(lp=np.log(pm.precio)).pivot_table(index=clave, columns="municipio_id", values="lp")
    return m


def _row_quantiles(x, qs):
    """Cuantiles por fila ignorando NaN (interpolación lineal, igual que pandas), vectorizado."""
    s = np.sort(x, axis=1)                      # NaN al final
    n = (~np.isnan(x)).sum(1)
    out = []
    for q in qs:
        h = (n - 1) * q
        lo = np.floor(h).astype(int).clip(0)
        hi = np.ceil(h).astype(int).clip(0)
        a = np.take_along_axis(s, lo[:, None], 1)[:, 0]
        b = np.take_along_axis(s, hi[:, None], 1)[:, 0]
        out.append(a + (b - a) * (h - lo))
    return out


def boot_brecha(pm, clave, universo, reps=500, seed=SEMILLA, min_mun=MIN_MUN):
    """IC90 de la brecha mediana entre productos remuestreando municipios (la unidad de muestreo).

    Cada réplica sortea municipios con reemplazo y recalcula P90/P10 de cada unidad y la mediana entre productos."""
    m = _matriz(pm[pm.producto.isin(universo)], clave)
    prod = m.index.get_level_values("producto") if isinstance(m.index, pd.MultiIndex) else m.index
    codes, _ = pd.factorize(prod)
    a = m.to_numpy()
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for r in range(reps):
        x = a[:, rng.integers(0, a.shape[1], a.shape[1])]
        ok = (~np.isnan(x)).sum(1) >= min_mun
        q10, q90 = _row_quantiles(x[ok], [.1, .9])
        g = pd.Series((np.exp(q90 - q10) - 1) * 100).groupby(codes[ok]).median()
        out[r] = g.median()
    return np.nanpercentile(out, [5, 95])


def boot_unidad(pm, reps=500, seed=SEMILLA, min_mun=MIN_MUN):
    """IC90 de la brecha P90/P10 de cada unidad remuestreando sus municipios."""
    m = _matriz(pm, UNIDAD)
    a = m.to_numpy()
    rng = np.random.default_rng(seed)
    out = np.full((reps, len(a)), np.nan)
    for r in range(reps):
        x = a[:, rng.integers(0, a.shape[1], a.shape[1])]
        q10, q90 = _row_quantiles(x, [.1, .9])
        v = (np.exp(q90 - q10) - 1) * 100
        v[(~np.isnan(x)).sum(1) < min_mun] = np.nan
        out[r] = v
    ic = np.nanpercentile(out, [5, 95], axis=0)
    return m.index.to_frame(index=False).assign(ic90_inf=ic[0], ic90_sup=ic[1])


def prueba_municipio(sp):
    """¿Los precios de tienda de una unidad difieren por municipio más de lo que difieren entre tiendas del mismo
    municipio? Prueba de Kruskal-Wallis (de rangos: no supone distribución normal y aguanta precios repetidos).
    Devuelve el valor p por unidad."""
    from scipy.stats import kruskal
    rows = []
    for k, g in sp.groupby(UNIDAD, sort=False):
        grupos = [v.to_numpy() for _, v in g.groupby("municipio_id").precio]
        if len(grupos) < 2 or g.precio.nunique() == 1:
            p = 1.0
        else:
            p = float(kruskal(*grupos).pvalue)
        rows.append((*k, len(grupos), len(g), p))
    return pd.DataFrame(rows, columns=UNIDAD + ["municipios_prueba", "tiendas_prueba", "p_valor"])


def azar(pm_tiendas, reps=200, seed=SEMILLA, min_mun=MIN_MUN):
    """Brecha que daría solo el azar: se reparten al azar las mismas tiendas entre los municipios de cada unidad.

    pm_tiendas: precios de tienda (una fila por tienda y unidad) ya filtrados al paso final. Se conserva cuántas
    tiendas tiene cada municipio. Devuelve por unidad: brecha observada, mediana y P95 de la brecha al azar y el
    valor p_azar (proporción de repartos al azar con brecha igual o mayor)."""
    x = pm_tiendas.sort_values(UNIDAD).reset_index(drop=True)
    x["u"] = x.groupby(UNIDAD, sort=False).ngroup()
    u, mun, lp = x.u.to_numpy(), x.municipio_id.to_numpy(), np.log(x.precio.to_numpy())

    def gaps(v):
        g = pd.DataFrame({"u": u, "m": mun, "lp": v}).groupby(["u", "m"]).lp.median()
        q = g.groupby(level=0).quantile([.1, .9]).unstack()
        return ((np.exp(q[0.9] - q[0.1]) - 1) * 100).to_numpy()

    obs = gaps(lp)
    rng = np.random.default_rng(seed)
    null = np.empty((reps, len(obs)))
    for r in range(reps):
        null[r] = gaps(lp[np.argsort(rng.random(len(u)) + u)])
    keys = x.drop_duplicates("u").set_index("u")[UNIDAD]
    out = keys.assign(brecha_pct=obs, azar_mediana=np.median(null, 0), azar_p95=np.percentile(null, 95, 0),
                      p_azar=((null >= obs - 1e-9).sum(0) + 1) / (reps + 1))
    out["exceso_pp"] = out.brecha_pct - out.azar_mediana
    return out.reset_index(drop=True)


def bh(p, q=0.10):
    """Benjamini-Hochberg: True si la unidad sobrevive con tasa de falsos descubrimientos q."""
    p = np.asarray(p)
    o = np.argsort(p)
    thr = q * np.arange(1, len(p) + 1) / len(p)
    ok = p[o] <= thr
    k = np.flatnonzero(ok).max() + 1 if ok.any() else 0
    res = np.zeros(len(p), bool)
    res[o[:k]] = True
    return res


def misma_cadena(sp, min_mun=MIN_MUN):
    """Brecha entre municipios quitando la cadena: precio de cada tienda frente a la mediana de su cadena en la
    misma unidad. Lo que queda es cuánto cambia el precio de la misma cadena entre municipios."""
    x = sp.copy()
    x["lp"] = np.log(x.precio)
    x["dev"] = x.lp - x.groupby(UNIDAD + ["cadena_comercial"]).lp.transform("median")
    m = x.groupby(UNIDAD + ["municipio_id"]).dev.median().reset_index()
    s = m.groupby(UNIDAD).dev.agg(municipios="size", q10=lambda v: v.quantile(.1), q90=lambda v: v.quantile(.9))
    s = s[s.municipios >= min_mun]
    s["brecha_pct"] = (np.exp(s.q90 - s.q10) - 1) * 100
    return s.reset_index()


def boot_embudo(pms, claves, universo, reps=500, seed=SEMILLA, min_mun=MIN_MUN):
    """IC90 de la brecha mediana de varios pasos con los MISMOS municipios sorteados en cada réplica.

    Sirve para el intervalo de diferencias entre pasos (p. ej., cuánto desaparece de la ingenua a la validada).
    pms: {paso: precios municipales}; claves: {paso: columnas de la unidad}. Devuelve {paso: arreglo de réplicas}."""
    mats = {p: _matriz(pm[pm.producto.isin(universo)], claves[p]) for p, pm in pms.items()}
    muns = sorted(set().union(*[m.columns for m in mats.values()]))
    rng = np.random.default_rng(seed)
    draws = [rng.integers(0, len(muns), len(muns)) for _ in range(reps)]
    out = {}
    for p, m in mats.items():
        a = m.reindex(columns=muns).to_numpy()
        prod = m.index.get_level_values("producto") if isinstance(m.index, pd.MultiIndex) else m.index
        codes, _ = pd.factorize(prod)
        v = np.empty(reps)
        for r, idx in enumerate(draws):
            x = a[:, idx]
            ok = (~np.isnan(x)).sum(1) >= min_mun
            q10, q90 = _row_quantiles(x[ok], [.1, .9])
            v[r] = pd.Series((np.exp(q90 - q10) - 1) * 100).groupby(codes[ok]).median().median()
        out[p] = v
    return out


def variante(d, clave, por_tienda=False, min_tiendas=MIN_TIENDAS):
    """Precios municipales con una sola validación, para medir cada paso por separado frente a la ingenua.

    clave: columnas que definen qué se compara; por_tienda: precio de tienda (mediana) y min_tiendas por municipio."""
    if not por_tienda:
        g = d.groupby(clave + ["municipio_id"], observed=True)
        return g.agg(precio=("precio_num", "mean"), tiendas=("establecimiento_id", "nunique")).reset_index()
    sp = d.groupby(clave + ["municipio_id", "establecimiento_id"], observed=True).precio_num.median() \
          .rename("precio").reset_index()
    sp["n"] = sp.groupby(clave + ["municipio_id"]).establecimiento_id.transform("size")
    sp = sp[sp.n >= min_tiendas]
    return sp.groupby(clave + ["municipio_id"]).agg(precio=("precio", "median"),
                                                    tiendas=("establecimiento_id", "size")).reset_index()


def tiendas_finales(d, min_tiendas=MIN_TIENDAS):
    """Precios de tienda del paso final (ajustados por día, sin posibles errores, municipios con min_tiendas)."""
    dia = indice_dia(d)
    x = d.assign(precio_aj=d.precio_num / np.exp(d.fecha.map(dia.efecto_log).fillna(0).to_numpy()))
    sp = marcar_errores(_tiendas(x, "precio_aj"))
    sp = sp[~sp.posible_error].copy()
    sp["tiendas_mun"] = sp.groupby(UNIDAD + ["municipio_id"]).establecimiento_id.transform("size")
    return sp[sp.tiendas_mun >= min_tiendas]
