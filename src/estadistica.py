# Copiado de _profeco_core/src/estadistica.py por publicar.py; no editar aquí.
"""Utilidades estadísticas comunes (tomadas de mexico-mismo-producto-precio, el análisis de referencia).

Unidad de muestreo: el municipio. Las tiendas de una misma ciudad no son independientes, así que los intervalos
remuestrean municipios. Semilla por defecto: 2026.

Contenido:
- store_prices: un precio por tienda y producto (mediana de sus observaciones en la quincena);
- flag_prices: posibles errores de captura y extremos, marcados sin borrar;
- sku_stats, classify, within_city_share, bootstrap_gap_within: dispersión del mismo producto entre tiendas;
- chain_index, chain_group_index, zone_pricing, same_chain_same_city: comparación de cadenas con el mismo
  producto en la misma ciudad (efectos fijos producto×municipio; IC90 por bootstrap de municipios);
- decompose, store_level: de cada 100 de diferencia, cuánto es cadena, ciudad, zona y sucursal
  (efectos fijos anidados, R² ajustado, Shapley; IC90 por jackknife de municipios);
- bootstrap_municipios: IC90 genérico de cualquier estadístico remuestreando municipios.

Convención: las funciones de dispersión, cadenas y descomposición esperan una tabla de precios de tienda
(salida de store_prices) con la clave de producto en una columna llamada `sku` (puede ser el sku_id del núcleo
o una clave propia, p. ej. sustancia + dosis + presentación) y las columnas precio, municipio_id,
cadena_comercial y establecimiento_id; decompose y store_level además usan mediana_nacional (flag_prices).
"""
import numpy as np
import pandas as pd

SEMILLA = 2026


def store_prices(obs, key, extra=(), price="precio_num"):
    """Un precio por tienda y producto: mediana de sus observaciones; guarda cuántas hubo y si cambiaron.

    key: columnas que definen el producto (p. ej. ["sku_id"] o ["producto", "presentacion", "marca"]).
    """
    cols = list(key) + list(extra) + ["giro", "estado", "municipio", "municipio_id", "cadena_comercial",
                                      "establecimiento_id"]
    cols = list(dict.fromkeys(cols))
    sp = obs.groupby(cols, dropna=False, as_index=False, observed=True).agg(
        precio=(price, "median"), observaciones=(price, "size"), precios_distintos=(price, "nunique"),
        precio_min=(price, "min"), precio_max=(price, "max"), dias=("fecha", "nunique"))
    sp["razon_max_min"] = sp.precio_max / sp.precio_min
    for c in sp.select_dtypes("category").columns:
        sp[c] = sp[c].astype(str)
    return sp


def bootstrap_municipios(d, stat, reps=200, seed=SEMILLA):
    """IC90 de stat(d) remuestreando municipios con reemplazo (un municipio repetido entra como copia)."""
    rng = np.random.default_rng(seed)
    rows = d.groupby("municipio_id", observed=True).indices
    muns = list(rows)
    vals = []
    for _ in range(reps):
        pick = rng.integers(0, len(muns), len(muns))
        idx = np.concatenate([rows[muns[i]] for i in pick])
        copy = np.concatenate([np.full(len(rows[muns[i]]), j) for j, i in enumerate(pick)])
        x = d.iloc[idx].copy()
        x["municipio_id"] = x.municipio_id.astype(str) + "#" + copy.astype(str)
        vals.append(stat(x))
    vals = np.array(vals, dtype=float)
    return np.nanpercentile(vals, [5, 95], axis=0), vals


# --------------------------------------------------------------------------- calidad
def flag_prices(sp, low=0.5, high=2.0, z=3.5, floor=0.10, sku="sku"):
    """Marca, sin borrar:
    - posible_error: precio < 0.5× o > 2× la mediana nacional del SKU (p. ej., pieza capturada como paquete);
    - extremo: |z robusto| > 3.5 en logaritmos dentro del SKU (z = desviación / max(1.4826 × MAD, 0.10)).
    """
    out = sp.copy()
    out["mediana_nacional"] = out.groupby(sku).precio.transform("median")
    out["razon_nacional"] = out.precio / out.mediana_nacional
    lr = np.log(out.razon_nacional)
    # Escala robusta con piso de 10 %: en SKUs donde casi todas las tiendas cobran igual, la MAD es 0 y
    # cualquier diferencia pequeña parecería extrema. Con el piso, «extremo» exige al menos ±42 %.
    mad = (lr.abs().groupby(out[sku]).transform("median") * 1.4826).clip(lower=floor)
    out["z_robusto"] = lr / mad
    out["posible_error"] = (out.razon_nacional < low) | (out.razon_nacional > high)
    out["extremo"] = out.posible_error | (np.abs(out.z_robusto) > z)
    return out


# --------------------------------------------------------------------------- dispersión
def add_local(d):
    """Mediana local (municipio) del SKU, número de tiendas en el municipio y relativos."""
    out = d.copy()
    g = out.groupby(["sku", "municipio_id"]).precio
    out["mediana_local"] = g.transform("median")
    out["tiendas_local"] = g.transform("size")
    out["rel_nacional_pct"] = (out.precio / out.mediana_nacional - 1) * 100
    out["rel_local_pct"] = (out.precio / out.mediana_local - 1) * 100
    return out


def sku_stats(d):
    """Estadísticos de precio por SKU: percentiles, brecha P90/P10, CV robusto y rango."""
    g = d.groupby("sku").precio
    st = pd.DataFrame({"tiendas": g.size(), "municipios": d.groupby("sku").municipio_id.nunique(),
                       "cadenas": d.groupby("sku").cadena_comercial.nunique(),
                       "minimo": g.min(), "p10": g.quantile(.1), "p25": g.quantile(.25), "mediana": g.median(),
                       "p75": g.quantile(.75), "p90": g.quantile(.9), "maximo": g.max()})
    st["brecha_p90_p10_pct"] = (st.p90 / st.p10 - 1) * 100
    st["cv_robusto_pct"] = (st.p75 - st.p25) / (1.349 * st.mediana) * 100
    st["rango_max_min_pct"] = (st.maximo / st.minimo - 1) * 100
    st["brecha_p90_p10_pesos"] = st.p90 - st.p10
    st["precio_modal_pct"] = d.groupby("sku").precio.agg(lambda s: s.value_counts(normalize=True).iloc[0] * 100)
    return st


def classify(st, low=5, high=30):
    """Clases de dispersión para comunicar: casi igual (≤5%), moderada, alta (>30%)."""
    return pd.cut(st.brecha_p90_p10_pct, [-1, low, high, np.inf],
                  labels=[f"Casi igual (≤{low}%)", f"Moderada ({low}–{high}%)", f"Alta (>{high}%)"])


def extremes(d, sku):
    """Tienda más barata y más cara del SKU (cadena y municipio)."""
    g = d[d.sku == sku].sort_values("precio")
    lo, hi = g.iloc[0], g.iloc[-1]
    return lo, hi


def within_city_share(d):
    """Parte de la variación del log(precio) de cada SKU que ocurre dentro del mismo municipio.

    Varianza total = Σ (log p − media del SKU)²; dentro = Σ (log p − media SKU×municipio)².
    """
    y = np.log(d.precio.to_numpy())
    sku = pd.factorize(d.sku)[0]
    cell = d.groupby(["sku", "municipio_id"], sort=False).ngroup().to_numpy()
    return _within(y, sku, cell)


def _within(y, sku, cell, w=None):
    w = np.ones(len(y)) if w is None else w
    def dev(g):
        sw = np.bincount(g, w)
        m = np.bincount(g, w * y) / np.where(sw > 0, sw, 1)
        return (w * (y - m[g]) ** 2).sum()
    return dev(cell) / dev(sku)


def median_gap(d):
    g = d.groupby("sku").precio
    return ((g.quantile(.9) / g.quantile(.1) - 1) * 100).median()


def bootstrap_gap_within(d, reps=200, seed=2026):
    """IC90 de (brecha P90/P10 mediana entre SKUs, % de la varianza dentro de la ciudad) remuestreando
    municipios: la ciudad es la unidad de muestreo. Un municipio repetido entra como copia independiente."""
    rng = np.random.default_rng(seed)
    rows = d.groupby("municipio_id").indices
    muns = list(rows)
    y_all = np.log(d.precio.to_numpy())
    sku_all = pd.factorize(d.sku)[0]
    cell_all = d.groupby(["sku", "municipio_id"], sort=False).ngroup().to_numpy()
    vals = []
    for _ in range(reps):
        pick = rng.integers(0, len(muns), len(muns))
        idx = np.concatenate([rows[muns[i]] for i in pick])
        copy = np.concatenate([np.full(len(rows[muns[i]]), j) for j, i in enumerate(pick)])
        x = d.iloc[idx]
        gap = median_gap(x)
        cell = pd.factorize(pd.Series(cell_all[idx]).astype(str) + "#" + pd.Series(copy).astype(str))[0]
        vals.append([gap, _within(y_all[idx], sku_all[idx], cell) * 100])
    vals = np.array(vals)
    return np.percentile(vals, [5, 95], axis=0), vals


def other_channels(other, sm, min_pairs=30):
    """Precio de la misma SKU en otro canal frente a la mediana de supermercados del mismo municipio."""
    ref = sm.groupby(["sku", "municipio_id"]).precio.median().rename("mediana_super").reset_index()
    x = other.merge(ref, on=["sku", "municipio_id"], how="inner")
    x["rel_pct"] = (x.precio / x.mediana_super - 1) * 100
    x["log_rel"] = np.log(x.precio / x.mediana_super)
    rows = []
    for giro, g in x.groupby("giro"):
        if len(g) < min_pairs:
            continue
        rows.append({"canal": giro, "precios_comparables": len(g), "skus": g.sku.nunique(),
                     "tiendas": g.establecimiento_id.nunique(), "municipios": g.municipio_id.nunique(),
                     "diferencia_mediana_pct": (np.exp(g.log_rel.median()) - 1) * 100,
                     "pct_mas_caro": (g.rel_pct > 0.5).mean() * 100,
                     "pct_igual": (g.rel_pct.abs() <= 0.5).mean() * 100,
                     "pct_mas_barato": (g.rel_pct < -0.5).mean() * 100})
    return pd.DataFrame(rows), x


def channel_ci(x, reps=200, seed=2026):
    """IC90 de la diferencia mediana de cada canal remuestreando municipios."""
    rng = np.random.default_rng(seed)
    out = {}
    for giro, g in x.groupby("giro"):
        muns = g.municipio_id.unique()
        by = {m: s.log_rel.to_numpy() for m, s in g.groupby("municipio_id")}
        vals = []
        for _ in range(reps):
            pick = rng.choice(muns, len(muns), replace=True)
            vals.append((np.exp(np.median(np.concatenate([by[m] for m in pick]))) - 1) * 100)
        out[giro] = np.percentile(vals, [5, 95])
    return out


# --------------------------------------------------------------------------- cadenas
OTRAS = "Otras"


def chain_label(d, keep):
    return np.where(d.cadena_comercial.isin(keep), d.cadena_comercial, OTRAS)


def _demean(a, cell):
    return a - pd.DataFrame(a).groupby(cell).transform("mean").to_numpy()


def _blocks(d, cats, cell):
    """X'X y X'y por municipio, con X = indicadoras de cadena (sin «Otras») ya centradas en la celda."""
    D = pd.get_dummies(pd.Categorical(d.c, categories=cats)).to_numpy(float)
    Xt = _demean(D, cell)[:, :-1]
    yt = _demean(np.log(d.precio.to_numpy())[:, None], cell)[:, 0]
    mun = d.municipio_id.to_numpy()
    xx, xy, names = [], [], []
    for m, ix in pd.Series(np.arange(len(d))).groupby(mun).indices.items():
        X = Xt[ix]
        xx.append(X.T @ X)
        xy.append(X.T @ yt[ix])
        names.append(m)
    return np.array(xx), np.array(xy), names


def _solve(xx, xy, w):
    A = np.tensordot(w, xx, axes=1)
    v = np.tensordot(w, xy, axes=1)
    ok = np.diag(A) > 1e-9
    b = np.full(len(v), np.nan)
    b[ok] = np.linalg.lstsq(A[np.ix_(ok, ok)], v[ok], rcond=None)[0]
    return b


def _center(b, cats, store_share):
    """Efectos frente a la tienda promedio (una tienda = un voto): Σ share × efecto = 0."""
    e = pd.Series(np.r_[b, 0.0], index=cats)
    s = store_share.reindex(cats).fillna(0)
    ok = e.notna()
    return e - (e[ok] * s[ok]).sum() / s[ok].sum()


def chain_index(d, keep, reps=500, seed=2026):
    """Índice de cada cadena (tienda promedio = 0 %) con IC90 por bootstrap de municipios.

    d: precios de tienda (una fila por tienda y SKU) con columnas sku, municipio_id, cadena_comercial,
    establecimiento_id y precio.
    """
    d = d.copy()
    d["c"] = chain_label(d, keep)
    cats = list(keep) + [OTRAS]
    cell = pd.factorize(d.sku.astype(str) + "|" + d.municipio_id)[0]
    xx, xy, muns = _blocks(d, cats, cell)
    stores = d.drop_duplicates("establecimiento_id")
    share = stores.c.value_counts(normalize=True)
    est = _center(_solve(xx, xy, np.ones(len(muns))), cats, share)
    rng = np.random.default_rng(seed)
    boot = np.empty((reps, len(cats)))
    for r in range(reps):
        w = np.bincount(rng.integers(0, len(muns), len(muns)), minlength=len(muns)).astype(float)
        boot[r] = _center(_solve(xx, xy, w), cats, share).to_numpy()
    pct = lambda v: (np.exp(v) - 1) * 100
    multi = pd.Series(cell).map(pd.Series(cell).value_counts()) > 1
    comp = d[multi.to_numpy()]
    out = pd.DataFrame({
        "cadena_comercial": cats, "efecto_pct": pct(est.to_numpy()),
        "ic90_inf": pct(np.nanpercentile(boot, 5, axis=0)), "ic90_sup": pct(np.nanpercentile(boot, 95, axis=0)),
        "tiendas": stores.c.value_counts().reindex(cats).fillna(0).astype(int).to_numpy(),
        "municipios": d.groupby("c").municipio_id.nunique().reindex(cats).fillna(0).astype(int).to_numpy(),
        "precios_comparables": comp.groupby("c").size().reindex(cats).fillna(0).astype(int).to_numpy(),
    })
    out["solido"] = (out.ic90_inf > 0) | (out.ic90_sup < 0)
    return out.sort_values("efecto_pct").reset_index(drop=True), boot


def chain_group_index(d, keep, groups, reps=200, seed=2026, min_stores=6):
    """Índice de cadena por grupo de productos (misma regresión, un grupo a la vez)."""
    rows = []
    for g_ in groups:
        sub = d[d.grupo == g_]
        t, _ = chain_index(sub, keep, reps=reps, seed=seed)
        t["grupo"] = g_
        rows.append(t)
    out = pd.concat(rows, ignore_index=True)
    out.loc[out.tiendas < min_stores, ["efecto_pct", "ic90_inf", "ic90_sup"]] = np.nan
    return out


def zone_pricing(d, keep, min_mun=5, tol=2.0, zone=5.0):
    """Clasifica cada par cadena–SKU presente en ≥ min_mun municipios.

    Precio de la cadena en un municipio = mediana de sus tiendas ahí. Brecha = P90/P10 de esos precios.
    Único: brecha ≤ tol %; ajuste leve: tol–zone %; por zona: > zone %.
    """
    x = d[d.cadena_comercial.isin(keep)]
    cp = x.groupby(["cadena_comercial", "sku", "municipio_id"]).precio.median().reset_index()
    g = cp.groupby(["cadena_comercial", "sku"]).precio
    z = pd.DataFrame({"municipios": g.size(), "p10": g.quantile(.1), "p90": g.quantile(.9),
                      "minimo": g.min(), "maximo": g.max(), "mediana": g.median()}).reset_index()
    z = z[z.municipios >= min_mun].copy()
    z["brecha_pct"] = (z.p90 / z.p10 - 1) * 100
    labels = ["Precio único", "Ajuste leve", "Precio por zona"]
    z["clase"] = pd.cut(z.brecha_pct, [-np.inf, tol, zone, np.inf], labels=labels)
    summ = (z.groupby("cadena_comercial").clase.value_counts(normalize=True).mul(100).unstack()
            .reindex(columns=labels).fillna(0))
    summ["pares"] = z.groupby("cadena_comercial").size()
    summ["municipios"] = x.groupby("cadena_comercial").municipio_id.nunique()
    summ["brecha_mediana_pct"] = z.groupby("cadena_comercial").brecha_pct.median()
    return z, summ.sort_values("Precio único", ascending=False)


def same_chain_same_city(d, keep, tol=2.0):
    """Sucursales de la misma cadena en la misma ciudad: ¿cobran lo mismo por el mismo SKU?"""
    x = d[d.cadena_comercial.isin(keep)]
    g = x.groupby(["cadena_comercial", "sku", "municipio_id"]).precio.agg(["size", "min", "max"])
    g = g[g["size"] >= 2]
    g["brecha_pct"] = (g["max"] / g["min"] - 1) * 100
    by = g.groupby(level=0).brecha_pct.agg(celdas="size", igual_pct=lambda s: (s <= tol).mean() * 100)
    return g.reset_index(), by


# --------------------------------------------------------------------------- descomposición
COMPONENTES = ["Cadena", "Ciudad", "Zona de la cadena", "Sucursal"]
EXPLICA = {
    "Cadena": "precio que la cadena pone a ese producto en todo el país",
    "Ciudad": "precio de ese producto en la ciudad, en todas sus tiendas",
    "Zona de la cadena": "la cadena cobra ese producto distinto en esa ciudad",
    "Sucursal": "dos sucursales de la misma cadena y ciudad cobran distinto",
}


def _means(y, w, g, ng):
    sw = np.bincount(g, w, ng)
    return (np.bincount(g, w * y, ng) / np.where(sw > 0, sw, 1))[g]


def _r2(y, w, fit, mu, k):
    """R² ajustado por grados de libertad (k = parámetros). Sin el ajuste, un modelo con miles de grupos de
    una sola tienda «explica» el ruido de esa tienda y se sobrestiman cadena, ciudad y zona."""
    n = w.sum()
    return 1 - ((w * (y - fit) ** 2).sum() / (n - k)) / ((w * (y - mu) ** 2).sum() / (n - 1))


def _two_way(y, w, a, na, b, nb, tol=1e-9, max_iter=1000):
    """Efectos fijos aditivos a + b por proyecciones alternadas (ponderado)."""
    fb = np.zeros_like(y)
    prev = np.inf
    for _ in range(max_iter):
        fa = _means(y - fb, w, a, na)
        fb = _means(y - fa, w, b, nb)
        ssr = (w * (y - fa - fb) ** 2).sum()
        if prev - ssr < tol * ssr:
            break
        prev = ssr
    return fa + fb


def shares(y, w, a, b, ab):
    """Participaciones (%) con a = cadena(×SKU), b = ciudad(×SKU), ab = cadena×ciudad(×SKU); códigos enteros."""
    mu = (w * y).sum() / w.sum()
    na, nb, nab = a.max() + 1, b.max() + 1, ab.max() + 1
    r_a = _r2(y, w, _means(y, w, a, na), mu, na)
    r_b = _r2(y, w, _means(y, w, b, nb), mu, nb)
    r_ab_add = _r2(y, w, _two_way(y, w, a, na, b, nb), mu, na + nb - 1)
    r_ab = _r2(y, w, _means(y, w, ab, nab), mu, nab)
    sh_a = (r_a + (r_ab_add - r_b)) / 2
    sh_b = (r_b + (r_ab_add - r_a)) / 2
    return pd.Series([sh_a, sh_b, r_ab - r_ab_add, 1 - r_ab], index=COMPONENTES) * 100


def _codes(d, by_sku=True):
    k = [d.sku] if by_sku else []
    a = d.groupby(k + [d.cadena_comercial], sort=False).ngroup().to_numpy()
    b = d.groupby(k + [d.municipio_id], sort=False).ngroup().to_numpy()
    ab = d.groupby(k + [d.cadena_comercial, d.municipio_id], sort=False).ngroup().to_numpy()
    return a, b, ab


def _jack(y, a, b, ab, mun):
    """Jackknife por municipio: participaciones sin cada ciudad y error estándar."""
    vals = []
    for m in np.unique(mun):
        k = mun != m
        vals.append(shares(y[k], np.ones(k.sum()), pd.factorize(a[k])[0], pd.factorize(b[k])[0],
                           pd.factorize(ab[k])[0]).to_numpy())
    vals = np.array(vals)
    n = len(vals)
    return np.sqrt((n - 1) / n * ((vals - vals.mean(axis=0)) ** 2).sum(axis=0))


def _table(est, se):
    out = pd.DataFrame({"participacion_pct": est, "error_estandar": se,
                        "ic90_inf": est - 1.645 * se, "ic90_sup": est + 1.645 * se})
    out["que_significa"] = out.index.map(EXPLICA)
    return out


def decompose(d, jackknife=True):
    """Componentes del precio del mismo SKU, con IC90 por jackknife de municipios."""
    y = np.log(d.precio / d.mediana_nacional).to_numpy()
    a, b, ab = _codes(d)
    est = shares(y, np.ones(len(y)), a, b, ab)
    mun = pd.factorize(d.municipio_id)[0]
    return _table(est, _jack(y, a, b, ab, mun) if jackknife else np.full(len(est), np.nan))


def store_level(d, jackknife=True):
    """Nivel general de cada tienda = promedio de log(precio / mediana nacional) de sus SKUs."""
    s = d.assign(y=np.log(d.precio / d.mediana_nacional)).groupby(
        ["establecimiento_id", "cadena_comercial", "municipio_id"], as_index=False).y.mean()
    y = s.y.to_numpy()
    a, b, ab = _codes(s, by_sku=False)
    est = shares(y, np.ones(len(y)), a, b, ab)
    mun = pd.factorize(s.municipio_id)[0]
    return _table(est, _jack(y, a, b, ab, mun) if jackknife else np.full(len(est), np.nan))
