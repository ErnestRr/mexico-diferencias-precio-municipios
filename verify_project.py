"""Verificación independiente: recalcula las cifras clave solo con pandas y numpy a partir de los precios originales
(Parquet de PROFECO), sin usar los módulos de src/, y comprueba que coinciden con resultados.json y con el README."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROC, META = ROOT / "data/processed", ROOT / "data/metadata"
README = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
RES = json.loads((PROC / "resultados.json").read_text(encoding="utf-8"))
SRC = PROC / "profeco_extracto.parquet"
if not SRC.exists():
    SRC = ROOT.parent / "_profeco_core/data/profeco_2026_08_q2.parquet"

COLS = ["producto", "presentacion", "marca", "catalogo", "giro", "cadena_comercial", "municipio_id", "establecimiento_id",
        "sku_id", "fecha", "precio_num", "cantidad_base", "unidad_base"]
d = pd.read_parquet(SRC, columns=COLS)
d = d[(d.precio_num > 0)].copy()
for c in d.columns:
    if isinstance(d[c].dtype, pd.CategoricalDtype) or d[c].dtype == object:
        d[c] = d[c].astype(str)
d = d[d.catalogo != "Medicamentos"]
d["pres_key"] = np.where(d.cantidad_base.notna(), d.cantidad_base.round(4).astype(str) + " " + d.unidad_base.astype(str),
                         "texto: " + d.presentacion)
U4 = ["producto", "pres_key", "marca", "giro"]


def p90p10(m, key):
    s = m.groupby(key).precio.agg(n="size", p10=lambda x: x.quantile(.1), p90=lambda x: x.quantile(.9)).reset_index()
    s = s[s.n >= 10]
    s["brecha"] = (s.p90 / s.p10 - 1) * 100
    return s


# Comparación ingenua: nombre de producto, promedio de todos los registros del municipio.
ing = p90p10(d.groupby(["producto", "municipio_id"]).precio_num.mean().rename("precio").reset_index(), ["producto"])
# Validada: precio ajustado por día de captura, mediana por tienda, sin posibles errores frente a su cadena,
# 3 tiendas o más por municipio, mediana municipal y 10 municipios o más.
lp = np.log(d.precio_num)
dia = (lp - lp.groupby([d.cadena_comercial, d.sku_id]).transform("mean")).groupby(d.fecha).mean()
d["aj"] = d.precio_num / np.exp(d.fecha.map(dia).fillna(0).to_numpy())
sp = d.groupby(U4 + ["municipio_id", "establecimiento_id", "cadena_comercial"]).aj.median().rename("precio").reset_index()
raz = sp.precio / sp.groupby(U4 + ["cadena_comercial"]).precio.transform("median")
sp = sp[(raz >= 0.5) & (raz <= 2.0)].copy()
sp["n"] = sp.groupby(U4 + ["municipio_id"]).establecimiento_id.transform("size")
val = p90p10(sp[sp.n >= 3].groupby(U4 + ["municipio_id"]).precio.median().reset_index(), U4)
universo = set(val.producto) & set(ing.producto)
b_ing = ing[ing.producto.isin(universo)].set_index("producto").brecha.median()
b_val = val[val.producto.isin(universo)].groupby("producto").brecha.median().median()
desap = (b_ing - b_val) / b_ing * 100

for nombre, calc, clave in [("ingenua", b_ing, "paso_ingenua"), ("validada", b_val, "validada"),
                            ("desaparece", desap, "desaparece_pct"), ("productos", len(universo), "productos_universo")]:
    ref = RES[clave]["cifra"]
    assert abs(calc - ref) < 0.05, f"{nombre}: recalculado {calc:.3f} contra {ref:.3f} en resultados.json"
    print(f"OK  {nombre:12s} {calc:,.2f} (resultados.json {ref:,.2f})")

checks = {"ingenua": f"{b_ing:.0f}%", "validada": f"{b_val:.1f}%", "desaparece": f"{desap:.0f}%",
          "productos": f"{len(universo)}", "sobreviven": f"{RES['n_articulos']['cifra']:,.0f} artículos comparables, solo {RES['n_sobreviven']['cifra']:.0f}"}
for name, computed in checks.items():
    assert computed in README, f"{name}: {computed} no aparece en el README"
    print(f"OK  {name:12s} {computed} aparece en el README")

for nb_path in sorted((ROOT / "notebooks").glob("0*.ipynb")):
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is not None, f"{nb_path.name} sin ejecutar"
            assert not any(o["output_type"] == "error" for o in cell["outputs"]), nb_path.name
for f in ["data/metadata/manifiesto_insumos.json", "data/metadata/parametros.json", "docs/index.html",
          "outputs/charts/01_embudo_comparabilidad.png", "outputs/charts/01_embudo_comparabilidad.svg",
          "outputs/charts/02_distribucion_ingenua_validada.png", "outputs/charts/03_casos_artefacto.png",
          "outputs/charts/04_casos_sobreviven.png", "outputs/charts/05_que_falta.png",
          "outputs/social/01_embudo_comparabilidad_horizontal.png", "outputs/social/01_embudo_comparabilidad_vertical.png"]:
    assert (ROOT / f).exists(), f"Falta {f}"
assert "elaboración propia con datos de PROFECO" in README
assert "URL oficial" in README
print("Verificación correcta: las cifras clave del README se reproducen de forma independiente "
      "y los notebooks se ejecutaron sin errores.")
