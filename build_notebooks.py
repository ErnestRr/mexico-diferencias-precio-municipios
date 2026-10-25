"""Genera los notebooks del proyecto. Después ejecutarlos en orden 00→05 (ver README)."""
from pathlib import Path
import nbformat as nbf
import yaml

root = Path(__file__).resolve().parent
CFG = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8")) or {}
OBJ = CFG.get("objetivo", "")
KERNEL = {"display_name": "Python (mexico-costo-canasta)", "language": "python", "name": "python3"}
SETUP = """import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
import entorno
entorno.setup()
import profeco, tablas, estadistica as E, charts as C
import embudo as M
PROC, META, CHARTS, SOCIAL = entorno.PROC, entorno.META, entorno.CHARTS, entorno.SOCIAL
CFG = entorno.config()
def reg(*a, **k):
    entorno.registrar(*a, **k)
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 70)
raw = entorno.load_raw()
d_all = M.prep(raw)
d = d_all[~d_all.catalogo.isin(M.FUERA_PRINCIPAL)].copy()      # universo principal
params = json.loads((META / "parametros.json").read_text(encoding="utf-8"))
REPS = params.get("bootstrap_replicas", 500)
"""


def write(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(c[1]) if c[0] == "md" else nbf.v4.new_code_cell(c[1]) for c in cells]
    nb.metadata.kernelspec = KERNEL
    (root / "notebooks").mkdir(exist_ok=True)
    nbf.write(nb, root / "notebooks" / name)


def head(num, title, question, why):
    return ("md", f"# {num} · {title}\n\n**Objetivo:** {OBJ}\n\n**Pregunta:** {question}\n\n{why}")


# --------------------------------------------------------------------------- 00
write("00_datos_y_cobertura.ipynb", [
    head("00", "Datos, cobertura y decisiones de comparabilidad", CFG.get("pregunta", ""),
         """Este notebook responde: ¿qué hay detrás de un «nombre de producto» en PROFECO, cuántas tiendas por municipio
hay para comparar, si las fechas de captura difieren entre municipios y qué precios son sospechosos? Con eso se fijan
el orden y los umbrales del embudo de comparabilidad. Cierra con la tabla de decisiones metodológicas.

Por qué importa: quien compara precios entre ciudades con un archivo público suele agrupar por nombre de producto y
sacar promedios. Si esa diferencia viene de comparar cosas distintas, cualquier decisión comercial basada en ella
parte de un error."""),
    ("code", SETUP.replace('params = json.loads((META / "parametros.json").read_text(encoding="utf-8"))\nREPS = params.get("bootstrap_replicas", 500)\n', "") + """manifest = entorno.write_manifest(raw)
params = {"semilla": M.SEMILLA, "bootstrap_replicas": 500, "repartos_azar": 200, "min_municipios": M.MIN_MUN,
          "min_tiendas": M.MIN_TIENDAS, "error_bajo": M.ERROR_BAJO, "error_alto": M.ERROR_ALTO,
          "fuera_principal": M.FUERA_PRINCIPAL, "fdr": 0.10, "min_relevante_pct": M.MIN_RELEVANTE}
_ = (META / "parametros.json").write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Registros con precio: {len(d_all):,} · tiendas: {d_all.establecimiento_id.nunique():,} · "
      f"municipios: {d_all.municipio_id.nunique()} · nombres de producto: {d_all.producto.nunique()}")
cob = d_all.groupby("catalogo").agg(registros=("precio_num", "size"), tiendas=("establecimiento_id", "nunique"),
                                    municipios=("municipio_id", "nunique"), nombres=("producto", "nunique"),
                                    articulos=("sku_id", "nunique")).sort_values("registros", ascending=False)
display(cob)"""),
    ("md", """## 1. Qué hay detrás de un nombre de producto

En PROFECO, el **nombre de producto** («Atún», «Refresco», «Folders») agrupa presentaciones, marcas y giros distintos.
Un **artículo** es la combinación exacta de nombre, presentación y marca."""),
    ("code", """k = d.groupby("producto").agg(presentaciones=("pres_key", "nunique"), marcas=("marca", "nunique"),
                               articulos=("sku_id", "nunique"), giros=("giro", "nunique"))
mezcla = pd.DataFrame({"% de nombres con más de una": (k > 1).mean() * 100, "mediana": k.median(), "máximo": k.max()})
display(mezcla.round(0))
ej = k.sort_values("articulos", ascending=False).head(8)
display(ej)
reg("pct_nombres_varias_presentaciones", (k.presentaciones > 1).mean() * 100, n=len(k), fuente="00_datos_y_cobertura",
    nota="% de nombres de producto (sin medicamentos) con más de una presentación")
reg("pct_nombres_varias_marcas", (k.marcas > 1).mean() * 100, n=len(k), fuente="00_datos_y_cobertura")"""),
    ("md", """**Decisión: el universo principal excluye medicamentos.** PROFECO no registra el laboratorio: «Losartán 50 mg
con 30 tabletas» puede ser de fabricantes distintos en dos tiendas. Así, el paso «misma marca» del embudo no se puede
completar para medicamentos. Se reportan aparte, como sensibilidad. Alternativa descartada: incluirlos en el resultado
principal; serían más de la mitad de los nombres de producto y su diferencia validada seguiría mezclando productos."""),
    ("md", """## 2. Periodo: ¿las fechas de captura difieren entre municipios?

La quincena tiene 12 días con captura. Si un municipio se capturó en un día con promociones y otro no, la diferencia
podría ser de fecha y no de lugar."""),
    ("code", """dm = d.groupby("municipio_id").fecha.agg(dias="nunique", primero="min", ultimo="max")
print("Días con captura por municipio:")
display(dm.dias.value_counts().sort_index().rename("municipios").to_frame().T)
sem = M.cambio_entre_semanas(d)
display(pd.Series(sem).round(2).to_frame("misma tienda y artículo en las dos semanas"))
dia = M.indice_dia(d)
dia["efecto_pct"] = (np.exp(dia.efecto_log) - 1) * 100
display(dia[["registros", "efecto_pct"]].round(2).T)
F = "00_datos_y_cobertura"
reg("municipios_un_dia", (dm.dias == 1).sum(), fuente=F)
reg("municipios_hasta_dos_dias", (dm.dias <= 2).sum(), fuente=F)
reg("pct_igual_semanas", sem["pct_igual"], n=sem["pares"], fuente=F, nota="misma tienda y artículo con el mismo precio en las dos semanas")
reg("pct_cambio5_semanas", sem["pct_cambio_mayor_5"], n=sem["pares"], fuente=F)
reg("efecto_dia_max", dia.loc[dia.registros > 1000, "efecto_pct"].abs().max(), fuente=F,
    nota="mayor efecto del día de captura (días con más de 1,000 registros), en %")"""),
    ("md", """**Decisión: ajustar cada precio por el efecto del día de captura y medir si el ajuste cambia algo.**
Hay municipios capturados en uno o dos días, así que las fechas sí difieren entre municipios. Pero el precio casi no
se mueve dentro de la quincena: el efecto del día (misma cadena y mismo artículo en días distintos) es de décimas de
punto. El paso «mismo periodo» del embudo divide cada precio entre el efecto de su día. Alternativas descartadas:
usar solo una semana (perdería la mitad de los municipios) o descartar municipios con un solo día (perdería ciudades
sin razón, si la fecha no mueve el precio). El 16 de agosto tiene solo 2 registros y no pesa."""),
    ("md", """## 3. Tiendas por municipio

Con una sola tienda, «el precio del municipio» es el precio de esa tienda: su cadena, su zona y sus errores. **Unidad
de comparación** = mismo nombre, presentación, marca y giro."""),
    ("code", """sp = M._tiendas(d)
dist_t = sp.drop_duplicates(M.UNIDAD + ["municipio_id"]).tiendas_mun
display(dist_t.describe(percentiles=[.1, .25, .5, .75, .9]).round(1).to_frame("tiendas por unidad y municipio").T)
umb = []
for t in (1, 2, 3, 5):
    x = sp[sp.tiendas_mun >= t].drop_duplicates(M.UNIDAD + ["municipio_id"])
    nm = x.groupby(M.UNIDAD).size()
    umb.append({"tiendas mínimas": t, "unidades con 10+ municipios": int((nm >= M.MIN_MUN).sum()),
                "nombres de producto": x[x.set_index(M.UNIDAD).index.isin(nm[nm >= M.MIN_MUN].index)].producto.nunique(),
                "% de pares unidad–municipio que quedan": len(x) / len(sp.drop_duplicates(M.UNIDAD + ["municipio_id"])) * 100})
umb = pd.DataFrame(umb)
display(umb.round(1))
reg("pct_unidad_mun_una_tienda", (dist_t == 1).mean() * 100, fuente=F, nota="% de pares unidad–municipio con una sola tienda")"""),
    ("md", """**Decisión: al menos 3 tiendas por municipio y 10 municipios por unidad.** El precio de cada tienda es la
mediana de sus observaciones y el del municipio, la mediana de sus tiendas. Con 3 tiendas, una sola no decide la
mediana; con 10 municipios, P10 y P90 dejan de ser el mínimo y el máximo. Sensibilidad con 2 y 5 tiendas en el
notebook 02. Alternativas descartadas: 1 tienda (el municipio sería una tienda) y 5 o más (deja fuera a la mitad de los
pares unidad–municipio y casi solo ciudades grandes)."""),
    ("md", """## 4. Calidad: posibles errores de captura"""),
    ("code", """q = M.marcar_errores(sp)
nac = sp.precio / sp.groupby(M.UNIDAD).precio.transform("median")
cal = pd.Series({"precios de tienda": len(q), "posible error contra su cadena": int(q.posible_error.sum()),
                 "posible error contra la mediana nacional": int(((nac < .5) | (nac > 2)).sum())})
display(cal.to_frame("conteo").T)
display(q[q.posible_error].sort_values("razon_cadena").head(6)[["producto", "pres_key", "marca", "cadena_comercial", "municipio_id",
                                                                  "precio", "razon_cadena"]])
reg("posibles_errores", int(q.posible_error.sum()), n=len(q), fuente=F, nota="precio fuera de 0.5×–2× la mediana de su cadena")
reg("posibles_errores_nacional", int(((nac < .5) | (nac > 2)).sum()), n=len(q), fuente=F)"""),
    ("md", """**Decisión: el posible error se mide contra la mediana de la propia cadena en la misma unidad** (menos de la
mitad o más del doble), se marca y no se borra; el embudo muestra la diferencia con y sin esos precios. Contra la
mediana nacional se marcarían como «error» diferencias reales entre municipios o cadenas, que son justo lo que se mide."""),
    ("md", """## 5. Medida y prueba"""),
    ("md", """- **Diferencia entre municipios de una unidad:** brecha P90/P10 de los precios municipales = cuánto más cuesta en
  el municipio caro típico que en el barato típico. No se usa máximo–mínimo, que depende de un solo municipio.
- **Diferencia de un nombre de producto:** mediana de sus unidades. **Del embudo:** mediana entre nombres de producto.
- **Universo fijo:** solo los nombres de producto que llegan al último paso, para que cada barra del embudo compare
  los mismos productos.
- **Comparación ingenua:** promedio simple de todos los registros con ese nombre en el municipio, como lo haría
  alguien sin revisar el dato.
- **IC90 (rango probable):** bootstrap de municipios, 500 réplicas, semilla 2026.
- **¿La diferencia es del municipio?** Prueba de rangos de Kruskal-Wallis: si los precios de tienda difieren entre
  municipios más que entre tiendas del mismo municipio. Con más de mil unidades, algunas saldrían «distintas» por azar;
  se controla con Benjamini-Hochberg al 10% (de cada 10 diferencias que se declaran, a lo más 1 sería falsa).
- **Referencia de azar:** la brecha que daría repartir al azar las mismas tiendas entre los municipios (200 repartos)."""),
    ("code", """res, prod, un, pm = M.embudo(d)
display(res.round(1))
reg("productos_universo", len(prod), fuente=F, nota="nombres de producto que llegan al último paso (sin medicamentos)")
reg("unidades_finales", int(res.iloc[-1].unidades), fuente=F)"""),
    ("md", "## 6. Decisiones metodológicas"),
    ("code", """t3 = umb.set_index("tiendas mínimas")
display(Markdown(f'''
| # | Decisión | Propuesta | Por qué | Alternativas descartadas |
|---|---|---|---|---|
| 1 | Punto de partida | comparación ingenua: nombre de producto y promedio de todos sus registros en el municipio | es lo que haría alguien sin revisar el dato; sirve de contraste | empezar ya validado (no mostraría qué se corrige) |
| 2 | Orden del embudo | 1 presentación → 2 marca → 3 giro → 4 tiendas → 5 periodo → 6 errores | primero se define **qué** se compara (el artículo) y después **cómo** se mide su precio; además se mide cada paso por separado | otro orden sin justificar; aplicar todo de golpe (no diría qué pesa) |
| 3 | Presentación | tamaño y unidad normalizados con `unidades.py`; si no se puede normalizar, texto literal | no se suponen equivalencias | precio por kg o litro entre tamaños (el tamaño cambia el precio unitario) |
| 4 | Marca | misma marca; los cruces entre marcas se ven en los análisis 5 y 8 | dos marcas no son el mismo producto | comparar marcas sin ajuste |
| 5 | Giro | supermercado contra supermercado, mercado contra mercado | el canal cambia el precio | mezclar giros |
| 6 | Tiendas | 3 o más por municipio; precio de tienda = mediana de su quincena | {(dist_t == 1).mean()*100:.0f}% de los pares unidad–municipio tienen 1 tienda | 1 tienda; 5 o más (deja {t3.loc[5, "unidades con 10+ municipios"]} unidades contra {t3.loc[3, "unidades con 10+ municipios"]}) |
| 7 | Periodo | ajustar por el efecto del día de captura (misma cadena y artículo) | {(dm.dias <= 2).sum()} municipios con 1 o 2 días de captura; el efecto del día es de décimas | solo una semana; quitar municipios de un día |
| 8 | Errores de captura | fuera de 0.5×–2× la mediana de su cadena; marcados, con y sin ellos | contra la mediana nacional se borrarían diferencias reales | borrar; usar la mediana nacional |
| 9 | Universo | sin medicamentos (aparte, como sensibilidad); 10+ municipios por unidad; universo fijo de nombres | PROFECO no trae laboratorio | incluirlos en el principal |
| 10 | Medida | brecha P90/P10 entre municipios; mediana entre nombres de producto | estándar de la serie; no depende de un municipio | máximo–mínimo; promedio (lo dominan unos cuantos nombres) |
| 11 | Incertidumbre | IC90 por bootstrap de municipios (500, semilla 2026); Kruskal-Wallis + Benjamini-Hochberg 10%; referencia de azar | el municipio es la unidad de muestreo; más de mil pruebas exigen control de falsos positivos | prueba sin corrección (1 de cada 20 saldría distinta por azar) |
| 12 | Oportunidad | no se calcula arbitraje ni rentabilidad; tabla de qué faltaría y si está en los datos | no hay costos, márgenes ni volumen | estimar márgenes con supuestos |
'''))"""),
    ("md", """**Conclusión.** 61% de los nombres de producto tiene más de una presentación y 59% más de una marca, y casi la
mitad (47%) de los pares unidad–municipio tiene una sola tienda: comparar a lo bruto mezcla todo eso. Las fechas de captura difieren
entre municipios, pero el precio casi no se mueve dentro de la quincena. El embudo valida en seis pasos, sobre un
universo fijo de nombres de producto y sin medicamentos."""),
])

# --------------------------------------------------------------------------- 01
Q = CFG.get("preguntas_secundarias", [""] * 5)
write("01_comparacion_ingenua.ipynb", [
    head("01", "La comparación ingenua", Q[0],
         """Por qué importa: es la cifra que aparece cuando alguien abre el archivo de PROFECO, agrupa por nombre de
producto y compara el promedio de cada municipio. Es el punto de partida del embudo y el contraste para todo lo demás.

**Correlación de rangos (Spearman)** = qué tanto se ordenan igual dos variables: 1 es el mismo orden, 0 ninguna relación.

**Decisión:** la diferencia entre municipios de un nombre de producto es la brecha P90/P10 de sus promedios
municipales (cuánto más cuesta en el municipio caro típico que en el barato típico). El universo son los 280 nombres
de producto que llegan validados al final del embudo (sin medicamentos), para comparar siempre lo mismo."""),
    ("code", SETUP + """C.register_cities(d_all.municipio_id.unique())
res, prod, un, pm = M.embudo(d)
U = set(prod.index)
bt = M.boot_embudo({"ingenua": pm["ingenua"]}, {"ingenua": ["producto"]}, U, reps=REPS)
lo, hi = np.percentile(bt["ingenua"], [5, 95])
F = "01_comparacion_ingenua"
reg("ingenua", prod.ingenua.median(), (lo, hi), n=len(prod), fuente=F, nota="brecha P90/P10 mediana entre nombres de producto, comparación ingenua")
print(f"Comparación ingenua: {prod.ingenua.median():.1f}% (IC90 {lo:.1f}–{hi:.1f}) en {len(prod)} nombres de producto")
display(prod.ingenua.describe(percentiles=[.1, .25, .5, .75, .9]).round(1).to_frame("brecha ingenua (%)").T)"""),
    ("md", """## 1. ¿Cuántas diferencias «parecen» oportunidad?

Umbrales de lectura: una diferencia de 30% o más entre el municipio caro típico y el barato típico es la que suele
llamar la atención en una presentación comercial."""),
    ("code", """umbr = pd.DataFrame({"umbral": [10, 20, 30, 50, 100]})
umbr["% de nombres por encima (ingenua)"] = [(prod.ingenua > u).mean() * 100 for u in umbr.umbral]
display(umbr.round(1))
reg("pct_ingenua_30", (prod.ingenua > 30).mean() * 100, n=len(prod), fuente=F, nota="% de nombres con brecha ingenua > 30%")
reg("pct_ingenua_50", (prod.ingenua > 50).mean() * 100, n=len(prod), fuente=F)
reg("ingenua_promedio", prod.ingenua.mean(), n=len(prod), fuente=F)"""),
    ("md", """## 2. Las diferencias ingenuas más grandes

Para cada nombre: cuántos artículos distintos mezcla (presentación × marca) y el promedio en el municipio barato y el
caro típicos (P10 y P90)."""),
    ("code", """mix = d.groupby("producto").agg(articulos=("sku_id", "nunique"), presentaciones=("pres_key", "nunique"),
                                 marcas=("marca", "nunique"), giros=("giro", "nunique"))
ing = un["ingenua"].set_index("producto").loc[sorted(U)].join(mix)
top = ing.sort_values("brecha_pct", ascending=False).head(12)
display(top[["municipios", "p10", "p90", "brecha_pct", "articulos", "presentaciones", "marcas", "giros"]].round(1))
rho = ing[["brecha_pct", "articulos", "presentaciones", "marcas"]].corr("spearman").brecha_pct
display(rho.round(2).to_frame("correlación de rangos con la brecha ingenua"))
reg("rho_articulos", rho["articulos"], n=len(ing), fuente=F, nota="Spearman entre brecha ingenua y número de artículos del nombre")
ing.reset_index().to_csv(PROC / "brecha_ingenua.csv", index=False, encoding="utf-8-sig")"""),
    ("md", """## 3. Con todo el archivo

Como contexto, la misma comparación ingenua con todos los nombres de producto que están en 10 municipios o más,
incluidos los medicamentos y los que no llegan al final del embudo."""),
    ("code", """todo = M.brechas(M.precios_municipales(d_all, "ingenua"), ["producto"])
reg("ingenua_todos_nombres", todo.brecha_pct.median(), n=len(todo), fuente=F)
print(f"Todos los nombres con 10+ municipios: {len(todo)} · brecha ingenua mediana {todo.brecha_pct.median():.1f}%")
v = entorno.cifras()
display(Markdown(f'''**Conclusión.** A lo bruto, el producto típico cuesta **{v["ingenua"]:.0f}% más** en el municipio caro
típico que en el barato típico (IC90 {v["ingenua_inf"]:.0f}–{v["ingenua_sup"]:.0f}%), y {v["pct_ingenua_30"]:.0f}% de los
nombres de producto superan 30%. El tamaño de esa diferencia casi no depende de cuántos artículos mezcle el nombre
(correlación de rangos {v["rho_articulos"]:.2f}): depende de qué presentación o marca domina en cada municipio, que es lo
que el embudo corrige.'''))"""),
])

# --------------------------------------------------------------------------- 02
write("02_embudo_de_comparabilidad.ipynb", [
    head("02", "El embudo de comparabilidad", Q[1],
         """Por qué importa: si la diferencia baja mucho al exigir que se compare lo mismo, la cifra ingenua no sirve
para decidir. Este notebook mide cuánto baja en cada paso y cuánto de lo que queda es más que azar.

**Decisión:** universo fijo (los mismos 280 nombres en cada paso) e IC90 con los mismos municipios sorteados en cada
paso, para que el intervalo de «cuánto desaparece» sea coherente. Alternativa descartada: recalcular el universo en
cada paso (la diferencia cambiaría solo porque cambian los productos)."""),
    ("code", SETUP + """res, prod, un, pm = M.embudo(d)
U = set(prod.index)
claves = {p: M.CLAVES.get(p, M.UNIDAD) for p in pm}
bt = M.boot_embudo(pm, claves, U, reps=REPS)
res["ic90_inf"] = [np.percentile(bt[p], 5) for p in res.paso]
res["ic90_sup"] = [np.percentile(bt[p], 95) for p in res.paso]
res["cambio_pp"] = res.brecha_mediana.diff()
res["nombre"] = [t for _, t, _ in M.PASOS]
res["que_exige"] = [x for _, _, x in M.PASOS]
display(res.round(1))
F = "02_embudo_de_comparabilidad"
for _, r_ in res.iterrows():
    reg(f"paso_{r_.paso}", r_.brecha_mediana, (r_.ic90_inf, r_.ic90_sup), n=r_.productos, fuente=F,
        nota=f"brecha mediana tras: {r_.nombre}")
    reg(f"unidades_{r_.paso}", r_.unidades, fuente=F)
ing, val = res.brecha_mediana.iloc[0], res.brecha_mediana.iloc[-1]
des = (bt["ingenua"] - bt["extremos"]) / bt["ingenua"] * 100
reg("desaparece_pct", (ing - val) / ing * 100, tuple(np.percentile(des, [5, 95])), n=len(prod), fuente=F,
    nota="% de la brecha ingenua que desaparece al validar")
reg("validada", val, (res.ic90_inf.iloc[-1], res.ic90_sup.iloc[-1]), n=len(prod), fuente=F)
reg("validada_promedio", res.brecha_promedio.iloc[-1], fuente=F)"""),
    ("md", """## 1. ¿Lo que queda es más que azar?

Aun si todos los municipios tuvieran exactamente los mismos precios, la brecha entre municipios no sería 0: cada
municipio tiene pocas tiendas y de cadenas distintas. **Referencia de azar** = la brecha que resulta de repartir al
azar las mismas tiendas entre los municipios, conservando cuántas tiene cada uno (200 repartos). Si la brecha validada
es parecida a esa referencia, la diferencia «entre municipios» es en realidad diferencia entre tiendas."""),
    ("code", """fin = un["extremos"][un["extremos"].producto.isin(U)]
sp = M.tiendas_finales(d).merge(fin[M.UNIDAD], on=M.UNIDAD)
az = M.azar(sp, reps=params["repartos_azar"])
az.to_csv(PROC / "azar_unidades.csv", index=False, encoding="utf-8-sig")
pa = az.groupby("producto")[["brecha_pct", "azar_mediana", "azar_p95"]].median()
pa["exceso_pp"] = pa.brecha_pct - pa.azar_mediana
display(pa.describe().round(1))
reg("azar", pa.azar_mediana.median(), n=len(pa), fuente=F, nota="brecha mediana si las tiendas se repartieran al azar entre municipios")
reg("exceso_pp", pa.exceso_pp.median(), n=len(pa), fuente=F, nota="puntos de brecha validada por encima del azar (mediana por nombre de producto)")
reg("pct_productos_sobre_p95", (pa.brecha_pct > pa.azar_p95).mean() * 100, n=len(pa), fuente=F)
prod = prod.join(pa[["azar_mediana", "exceso_pp"]])
prod.reset_index().to_csv(PROC / "brecha_producto_paso.csv", index=False, encoding="utf-8-sig")
res.to_csv(PROC / "embudo.csv", index=False, encoding="utf-8-sig")
queda = max(pa.exceso_pp.median(), 0)
reg("desaparece_azar_pct", (ing - queda) / ing * 100, n=len(pa), fuente=F,
    nota="% de la brecha ingenua que no es comparable o no supera al azar")"""),
    ("md", """## 2. Cada validación por separado

El orden del embudo atribuye a cada paso lo que cambia después de los anteriores. Para ver cuánto pesa cada validación
sin depender del orden, se aplica **sola** sobre la comparación ingenua."""),
    ("code", """sep = []
for nombre, clave, tienda in [("Misma presentación", ["producto", "pres_key"], False), ("Misma marca", ["producto", "marca"], False),
                              ("Mismo giro", ["producto", "giro"], False), ("3 tiendas o más", ["producto"], True)]:
    b_ = M.brechas(M.variante(d, clave, tienda), clave)
    s = b_[b_.producto.isin(U)].groupby("producto").brecha_pct.median()
    sep.append({"validación sola": nombre, "nombres": len(s), "brecha mediana": s.median(), "cambio frente a la ingenua (pp)": s.median() - ing})
sep = pd.DataFrame(sep)
display(sep.round(1))
sep.to_csv(PROC / "pasos_por_separado.csv", index=False, encoding="utf-8-sig")
for _, r_ in sep.iterrows():
    reg("sola_" + {"Misma presentación": "presentacion", "Misma marca": "marca", "Mismo giro": "giro", "3 tiendas o más": "tiendas"}[r_["validación sola"]],
        r_["brecha mediana"], n=r_["nombres"], fuente=F)"""),
    ("md", """## 3. Sensibilidad

Cada variante recalcula el embudo completo con su propio universo de nombres de producto."""),
    ("code", """def corrida(x, etiqueta, **kw):
    r_, p_, *_ = M.embudo(x, **kw)
    return {"variante": etiqueta, "nombres": len(p_), "ingenua": r_.brecha_mediana.iloc[0], "validada": r_.brecha_mediana.iloc[-1],
            "% que desaparece": (1 - r_.brecha_mediana.iloc[-1] / r_.brecha_mediana.iloc[0]) * 100}
sens = [{"variante": "Principal (3 tiendas, sin errores)", "nombres": len(prod), "ingenua": ing, "validada": val, "% que desaparece": (1 - val / ing) * 100},
        {"variante": "Con todos los precios (incluye posibles errores)", "nombres": len(prod), "ingenua": ing,
         "validada": res.brecha_mediana.iloc[-2], "% que desaparece": (1 - res.brecha_mediana.iloc[-2] / ing) * 100},
        corrida(d, "2 tiendas o más por municipio", min_tiendas=2),
        corrida(d, "5 tiendas o más por municipio", min_tiendas=5),
        corrida(d[d.semana == 1], "Solo semana 1 (17–21 ago)"),
        corrida(d[d.semana == 2], "Solo semana 2 (24–31 ago)"),
        corrida(d_all[d_all.catalogo.isin(M.FUERA_PRINCIPAL)], "Solo medicamentos (sin laboratorio)")]
sens = pd.DataFrame(sens)
display(sens.round(1))
sens.to_csv(PROC / "sensibilidad_embudo.csv", index=False, encoding="utf-8-sig")
for k, i in {"t2": 2, "t5": 3, "sem1": 4, "sem2": 5, "med": 6}.items():
    reg(f"sens_{k}_ingenua", sens.ingenua[i], n=sens.nombres[i], fuente=F)
    reg(f"sens_{k}_validada", sens.validada[i], n=sens.nombres[i], fuente=F)
reg("sens_todos_validada", sens.validada[1], fuente=F)"""),
    ("code", """v = entorno.cifras()
display(Markdown(f'''**Conclusión.** Al validar, la diferencia típica entre municipios baja de **{v["paso_ingenua"]:.0f}%** a
**{v["validada"]:.1f}%** (IC90 {v["validada_inf"]:.1f}–{v["validada_sup"]:.1f}%): desaparece {v["desaparece_pct"]:.0f}%
(IC90 {v["desaparece_pct_inf"]:.0f}–{v["desaparece_pct_sup"]:.0f}%). Los pasos que más pesan son la presentación y el
número de tiendas; el periodo y los errores de captura casi no cambian nada. Lo que queda ({v["validada"]:.1f}%) es casi
lo que daría repartir las tiendas al azar ({v["azar"]:.1f}%): en el producto típico, la diferencia propia del municipio
es de {v["exceso_pp"]:.1f} puntos.'''))"""),
])

# --------------------------------------------------------------------------- 03
write("03_diferencias_que_sobreviven.ipynb", [
    head("03", "Las diferencias que sobreviven", Q[2],
         """Por qué importa: una diferencia que sobrevive a la validación y a la prueba contra el azar es la única que
vale la pena investigar con costos, márgenes y demanda.

**Decisión:** para cada artículo comparable (mismo nombre, presentación, marca y giro, con 3 tiendas o más en 10
municipios o más) se prueba si sus precios de tienda difieren entre municipios más que entre tiendas del mismo
municipio (Kruskal-Wallis), con control de falsos positivos de Benjamini-Hochberg al 10%. Alternativa descartada: la
prueba sin corrección, que con más de mil artículos declara «distintos» a unos 50 solo por azar."""),
    ("code", SETUP + """C.register_cities(d_all.municipio_id.unique())
res, prod, un, pm = M.embudo(d)
U = set(prod.index)
fin = un["extremos"][un["extremos"].producto.isin(U)]
sp = M.tiendas_finales(d).merge(fin[M.UNIDAD], on=M.UNIDAD)
kw = M.prueba_municipio(sp)
kw["sobrevive"] = M.bh(kw.p_valor, params["fdr"])
ic = M.boot_unidad(pm["extremos"].merge(fin[M.UNIDAD], on=M.UNIDAD), reps=REPS)
mc = M.misma_cadena(sp).rename(columns={"brecha_pct": "misma_cadena_pct"})[M.UNIDAD + ["misma_cadena_pct"]]
az = pd.read_csv(PROC / "azar_unidades.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
for c in ["brecha_pct", "azar_mediana", "azar_p95", "p_azar", "exceso_pp"]:
    az[c] = az[c].astype(float)
f = (fin.merge(kw, on=M.UNIDAD).merge(ic, on=M.UNIDAD).merge(mc, on=M.UNIDAD, how="left")
        .merge(az[M.UNIDAD + ["azar_mediana", "azar_p95"]], on=M.UNIDAD, how="left"))
info = d.groupby(M.UNIDAD).agg(catalogo=("catalogo", "first"), categoria=("categoria", "first")).reset_index()
f = f.merge(info, on=M.UNIDAD, how="left")
F = "03_diferencias_que_sobreviven"
print(f"Artículos comparables: {len(f):,} · p<0.05 sin corrección: {(f.p_valor < .05).sum()} · sobreviven con corrección: {f.sobrevive.sum()}")
reg("n_articulos", len(f), fuente=F)
reg("n_sobreviven", f.sobrevive.sum(), n=len(f), fuente=F, nota="artículos con diferencia entre municipios tras Benjamini-Hochberg 10%")
reg("pct_sobreviven", f.sobrevive.mean() * 100, n=len(f), fuente=F)
reg("n_p05", (f.p_valor < .05).sum(), n=len(f), fuente=F)
reg("esperados_azar_p05", len(f) * 0.05, fuente=F)"""),
    ("md", """## 1. ¿Qué tienen en común los que sobreviven?

**Familia** = agrupación para leer el resultado: bebidas (refresco, cerveza, agua, jugo), tortilla, frescos y a granel
(frutas, verduras, carne, pan de mostrador, huevo) y otros."""),
    ("code", """def familia(row):
    p = row.producto.lower()
    if any(k in p for k in ["refresco", "cerveza", "agua", "jugo"]):
        return "Bebidas"
    if "tortilla" in p:
        return "Tortilla"
    if row.catalogo in ("Frutas y Legumbres", "Pescados y Mariscos", "Mercados") or any(k in p for k in ["carne", "bolillo", "huevo", "pollo"]):
        return "Frescos y a granel"
    return "Otros"
f["familia"] = f.apply(familia, axis=1)
fam = f.groupby("familia").agg(articulos=("sobrevive", "size"), sobreviven=("sobrevive", "sum"))
fam["% que sobrevive"] = fam.sobreviven / fam.articulos * 100
display(fam.round(1))
cmp_ = f.groupby("sobrevive")[["brecha_pct", "azar_mediana", "misma_cadena_pct", "municipios"]].median()
display(cmp_.round(1))
for k in fam.index:
    key = {"Bebidas": "bebidas", "Tortilla": "tortilla", "Frescos y a granel": "frescos", "Otros": "otros"}[k]
    reg(f"sob_{key}", fam.loc[k, "sobreviven"], n=fam.loc[k, "articulos"], fuente=F)
    reg(f"pct_sob_{key}", fam.loc[k, "% que sobrevive"], n=fam.loc[k, "articulos"], fuente=F)
reg("brecha_sobreviven", cmp_.loc[True, "brecha_pct"], fuente=F)
reg("brecha_no_sobreviven", cmp_.loc[False, "brecha_pct"], fuente=F)
reg("cadena_sobreviven", cmp_.loc[True, "misma_cadena_pct"], fuente=F, nota="brecha entre municipios de la misma cadena, artículos que sobreviven")
reg("cadena_no_sobreviven", cmp_.loc[False, "misma_cadena_pct"], fuente=F)"""),
    ("md", """**Lectura.** En los artículos que sobreviven, la misma cadena también cobra distinto según el municipio: la
diferencia no es solo qué cadenas hay en cada lugar. En los que no sobreviven, la misma cadena cobra casi igual en
todas partes."""),
    ("md", """## 2. Dónde está la diferencia: municipio caro y barato típicos"""),
    ("code", """pmf = pm["extremos"].merge(f.loc[f.sobrevive, M.UNIDAD], on=M.UNIDAD)
def extremos_mun(g):
    g = g.sort_values("precio")
    q10, q90 = g.precio.quantile(.1), g.precio.quantile(.9)
    lo = g.iloc[(g.precio - q10).abs().argmin()]
    hi = g.iloc[(g.precio - q90).abs().argmin()]
    return pd.Series({"mun_barato": C.city(lo.municipio_id), "precio_barato": lo.precio, "mun_caro": C.city(hi.municipio_id),
                      "precio_caro": hi.precio, "mediana": g.precio.median()})
ext = pmf.groupby(M.UNIDAD).apply(extremos_mun, include_groups=False).reset_index()
sob = f[f.sobrevive].merge(ext, on=M.UNIDAD)
# Relevante: además de pasar la prueba, la diferencia es de 10% o más y su IC90 queda arriba de lo típico del azar.
sob["relevante"] = (sob.brecha_pct >= M.MIN_RELEVANTE) & (sob.ic90_inf > sob.azar_mediana)
sob["etiqueta"] = [M.etiqueta(a, b_, c_, e_) for a, b_, c_, e_ in zip(sob.producto, sob.pres_key, sob.marca, sob.presentacion)]
sob = sob.sort_values(["relevante", "p_valor"], ascending=[False, True])
cols = ["etiqueta", "producto", "pres_key", "presentacion", "marca", "giro", "familia", "municipios", "brecha_pct", "ic90_inf", "ic90_sup",
        "azar_mediana", "azar_p95", "misma_cadena_pct", "mun_barato", "precio_barato", "mun_caro", "precio_caro", "p_valor", "relevante"]
display(sob[cols].round(2))
rel = sob[sob.relevante]
reg("n_relevantes", len(rel), n=len(sob), fuente=F, nota="sobreviven, brecha >= 10% e IC90 inferior arriba de la mediana del azar")
for fam_, key in [("Bebidas", "bebidas"), ("Tortilla", "tortilla"), ("Frescos y a granel", "frescos"), ("Otros", "otros")]:
    reg(f"rel_{key}", (rel.familia == fam_).sum(), fuente=F)
reg("brecha_relevantes", rel.brecha_pct.median(), n=len(rel), fuente=F)
reg("cadena_relevantes", rel.misma_cadena_pct.median(), n=len(rel), fuente=F)
f.to_csv(PROC / "articulos_prueba.csv", index=False, encoding="utf-8-sig")
sob[cols].to_csv(PROC / "sobrevivientes.csv", index=False, encoding="utf-8-sig")"""),
    ("md", """## 3. Casos que sobreviven

**Decisión:** un caso por familia (bebidas, tortilla, frescos), el relevante de menor valor p en cada una. Se reporta
la brecha con su IC90 y la referencia de azar del mismo artículo."""),
    ("code", """casos = []
for fam_, key in [("Tortilla", "tortilla"), ("Bebidas", "bebida"), ("Frescos y a granel", "fresco")]:
    s = sob[(sob.familia == fam_) & sob.relevante]
    if not len(s):
        continue
    c = s.iloc[0]
    casos.append(c)
    giro_txt = M.giro_corto(c.giro, plural=True)
    reg(f"caso_{key}_brecha", c.brecha_pct, (c.ic90_inf, c.ic90_sup), n=c.municipios, fuente=F,
        nota=f"{c.producto} · {c.pres_key} · {c.marca} · {giro_txt}")
    reg(f"caso_{key}_nombre", f"{c.etiqueta} en {giro_txt}", fuente=F)
    reg(f"caso_{key}_mun_barato", c.mun_barato, fuente=F)
    reg(f"caso_{key}_mun_caro", c.mun_caro, fuente=F)
    reg(f"caso_{key}_municipios", c.municipios, fuente=F)
    reg(f"caso_{key}_azar", c.azar_mediana, fuente=F)
    reg(f"caso_{key}_cadena", c.misma_cadena_pct, fuente=F)
    reg(f"caso_{key}_barato", c.precio_barato, fuente=F, nota=c.mun_barato)
    reg(f"caso_{key}_caro", c.precio_caro, fuente=F, nota=c.mun_caro)
casos = pd.DataFrame(casos)
display(casos[cols].round(2))
casos[cols].to_csv(PROC / "casos_sobreviven.csv", index=False, encoding="utf-8-sig")"""),
    ("md", """## 4. Lo que no resultó sólido"""),
    ("md", """- **Distintos pero pequeños:** pasan la prueba, pero la diferencia es menor a 10% o su IC90 toca lo típico del azar.
  Estadísticamente distintos no es lo mismo que relevantes para el negocio.
- **Distintos sin corregir:** con la prueba sin corrección (valor p < 0.05) parecerían distintos, pero no sobreviven al
  control de falsos positivos."""),
    ("code", """fragil = sob[~sob.relevante]
reg("sob_no_relevantes", len(fragil), n=len(sob), fuente=F, nota="sobreviven a la prueba pero con brecha < 10% o IC90 que toca la mediana del azar")
reg("p05_no_sobreviven", ((f.p_valor < .05) & ~f.sobrevive).sum(), fuente=F)
display(fragil[cols].round(2))
v = entorno.cifras()
display(Markdown(f'''**Conclusión.** De {v["n_articulos"]:,.0f} artículos comparables, **{v["n_sobreviven"]:.0f}
({v["pct_sobreviven"]:.0f}%)** tienen una diferencia entre municipios que supera la prueba con control de falsos
positivos, y solo **{v["n_relevantes"]:.0f}** con una diferencia de 10% o más claramente arriba del azar:
{v["rel_bebidas"]:.0f} bebidas, {v["rel_frescos"]:.0f} frescos, {v["rel_tortilla"]:.0f} de tortilla y {v["rel_otros"]:.0f} de otros
productos. En los que sobreviven, la misma cadena cobra {v["cadena_sobreviven"]:.0f}% más en el municipio caro típico,
contra {v["cadena_no_sobreviven"]:.1f}% en los demás. {v["p05_no_sobreviven"]:.0f} artículos parecían distintos sin corregir y
no sobreviven.'''))"""),
])

# --------------------------------------------------------------------------- 04
write("04_artefactos_y_lo_que_falta.ipynb", [
    head("04", "Artefactos y lo que falta para hablar de oportunidad", Q[3] + " " + Q[4],
         """Por qué importa: los ejemplos concretos muestran cómo nace una diferencia falsa; la tabla final separa lo
que dicen los precios públicos de lo que haría falta para decidir.

**Decisión:** los casos de artefacto se eligen con una regla y no a mano: en cada paso, el nombre de producto cuya
diferencia más baja con esa validación. Alternativa descartada: escoger ejemplos «bonitos», que exagerarían el efecto."""),
    ("code", SETUP + """C.register_cities(d_all.municipio_id.unique())
res, prod, un, pm = M.embudo(d)
U = set(prod.index)
F = "04_artefactos_y_lo_que_falta"
pasos = list(prod.columns)
caida = pd.DataFrame({p: prod[pasos[i - 1]] - prod[p] for i, p in enumerate(pasos) if i > 0})
display(caida.describe().round(1))

def cerca(g, q):
    return g.iloc[(g.precio - g.precio.quantile(q)).abs().argmin()]

def mezcla(producto, col, mun):
    x = d[(d.producto == producto) & (d.municipio_id == mun)]
    s = x.groupby(col).precio_num.agg(["size", "mean"]).sort_values("size", ascending=False)
    top = s.index[0]
    return top, s.loc[top, "size"] / s["size"].sum() * 100, s.loc[top, "mean"], x.precio_num.mean()

def texto_val(v, col):
    if col == "pres_key":
        return M.presentacion_corta(v)
    if col == "marca":
        return M.marca_corta(v) or "sin marca"
    return M.giro_corto(v)"""),
    ("md", """## 1. Cinco casos donde la diferencia ingenua era un artefacto"""),
    ("code", """casos = []
# Presentación, marca y giro: el municipio caro y el barato típicos registran mezclas distintas del mismo nombre.
for paso, col, tipo in [("presentacion", "pres_key", "Presentación distinta"), ("marca", "marca", "Otra marca"),
                        ("giro", "giro", "Otro giro")]:
    # El nombre que más baja con esta validación y cuyo municipio caro y barato típicos registran mezclas distintas.
    for p in caida[paso].sort_values(ascending=False).index[:25]:
        g = pm["ingenua"][pm["ingenua"].producto == p]
        lo, hi = cerca(g, .1), cerca(g, .9)
        tl, sl, ml, al = mezcla(p, col, lo.municipio_id)
        th, sh, mh, ah = mezcla(p, col, hi.municipio_id)
        if tl != th:
            break
    expl = (f"En {C.city(hi.municipio_id)} el promedio es {C.money(ah)} y {sh:.0f}% de los registros son "
            f"{texto_val(th, col)}; en {C.city(lo.municipio_id)} es {C.money(al)} y {sl:.0f}% son {texto_val(tl, col)}.")
    casos.append({"tipo": tipo, "producto": p, "ingenua": prod.loc[p, "ingenua"], "antes": prod.loc[p, pasos[pasos.index(paso) - 1]],
                  "despues": prod.loc[p, paso], "validada": prod.loc[p, "extremos"], "explicacion": expl})
# Una sola tienda: el artículo del paso «giro» cuya brecha más baja al exigir 3 tiendas.
ug, ut = un["giro"], un["tiendas"]
m = ug.merge(ut[M.UNIDAD + ["brecha_pct"]], on=M.UNIDAD, how="left", suffixes=("", "_t"))
m = m[m.producto.isin(U)]
m["caida"] = m.brecha_pct - m.brecha_pct_t.fillna(np.nan)
r1 = m.sort_values("caida", ascending=False).iloc[0]
key = (pm["giro"][M.UNIDAD] == r1[M.UNIDAD].values).all(axis=1)
g = pm["giro"][key]
g1 = g[g.tiendas == 1]
hi = g1.iloc[np.abs(np.log(g1.precio / g.precio.median())).argmax()]
ob = d[(d.municipio_id == hi.municipio_id) & (d[M.UNIDAD] == r1[M.UNIDAD].values).all(axis=1)]
cad = C.chain(ob.cadena_comercial.mode()[0])
nom = f"{r1.producto} {M.marca_corta(r1.marca)}".strip()
expl = (f"{nom}: en {C.city(hi.municipio_id)} el «precio del municipio» era el de una sola tienda ({cad}, "
        f"{C.money(hi.precio)}, contra {C.money(g.precio.median())} en el municipio típico); con 3 tiendas o más, la "
        f"diferencia del artículo baja de {r1.brecha_pct:.0f}% a {r1.brecha_pct_t:.0f}%.")
casos.append({"tipo": "Una sola tienda", "producto": r1.producto, "ingenua": prod.loc[r1.producto, "ingenua"],
              "antes": r1.brecha_pct, "despues": r1.brecha_pct_t, "validada": prod.loc[r1.producto, "extremos"], "explicacion": expl})
# Captura errónea: el posible error con mayor razón frente a su cadena entre los artículos del universo.
spe = M.marcar_errores(M._tiendas(d))
e = spe[spe.posible_error & spe.producto.isin(U) & (spe.tiendas_mun >= 3)].copy()
e["dist"] = np.abs(np.log(e.razon_cadena))
e1 = e.sort_values("dist", ascending=False).iloc[0]
med = e1.precio / e1.razon_cadena
veces = f"{1 / e1.razon_cadena:.0f} veces menos que" if e1.razon_cadena < 1 else f"{e1.razon_cadena:.0f} veces"
expl = (f"{M.etiqueta(e1.producto, e1.pres_key, e1.marca, e1.presentacion)}: una tienda {C.chain(e1.cadena_comercial)} en "
        f"{C.city(e1.municipio_id)} registró {C.money(e1.precio)}, {veces} la mediana de su cadena ({C.money(med)}). "
        "Se marca y se excluye; no se borra del archivo.")
casos.append({"tipo": "Captura errónea", "producto": e1.producto, "ingenua": prod.loc[e1.producto, "ingenua"],
              "antes": prod.loc[e1.producto, "periodo"], "despues": prod.loc[e1.producto, "extremos"],
              "validada": prod.loc[e1.producto, "extremos"], "explicacion": expl})
casos = pd.DataFrame(casos)
display(casos.round(1))
casos.to_csv(PROC / "casos_artefacto.csv", index=False, encoding="utf-8-sig")
for i, c in casos.iterrows():
    reg(f"art{i + 1}_ingenua", c.ingenua, fuente=F, nota=f"{c.tipo}: {c.producto}")
    reg(f"art{i + 1}_validada", c.validada, fuente=F, nota=f"{c.tipo}: {c.producto}")
    reg(f"art{i + 1}_antes", c.antes, fuente=F)
    reg(f"art{i + 1}_despues", c.despues, fuente=F)
    reg(f"art{i + 1}_producto", c.producto, fuente=F)
    reg(f"art{i + 1}_explicacion", c.explicacion, fuente=F)"""),
    ("md", """## 2. Qué haría falta para hablar de oportunidad

Una diferencia de precio al consumidor que sobrevive a la validación es una **pregunta**, no una oportunidad. Para
saber si conviene actuar hacen falta datos que el archivo de PROFECO no tiene. **No se calcula arbitraje ni
rentabilidad**: sin costos ni márgenes, cualquier cifra sería un supuesto. Las fuentes de INEGI se mencionan solo como
siguiente paso; no se usaron."""),
    ("code", """falta = pd.DataFrame([
    ["Costos de adquisición y logística", "No", "Nada: PROFECO registra solo el precio de anaquel",
     "Cotizaciones de proveedores, tarifas de flete y distancias a centros de distribución (datos propios)"],
    ["Márgenes", "No", "Nada: sin costo no hay margen",
     "Estados financieros por plaza o categoría (datos propios)"],
    ["Demanda y volumen", "No", "Nada: no hay ventas ni piezas vendidas",
     "Ventas propias por plaza; como siguiente paso, gasto de los hogares por región (INEGI, ENIGH)"],
    ["Competencia y características del mercado", "Parcial", "Cadenas y tiendas monitoreadas en cada municipio",
     "Número de establecimientos por municipio y giro (INEGI, DENUE y Censos Económicos)"],
    ["Tamaño de la población", "No", "Nada en el archivo de precios",
     "Población por municipio (INEGI, Censo de Población y Vivienda)"],
    ["Precio en tiendas no monitoreadas", "No", "Solo tiendas que visita PROFECO",
     "Levantamiento propio de precios en la plaza"],
    ["Estabilidad en el tiempo", "Parcial", "Una quincena; el precio casi no cambia entre semanas",
     "Varias quincenas de PROFECO para ver si la diferencia persiste"],
], columns=["Qué se necesitaría", "¿Está en los datos usados?", "Qué sí hay", "Dónde podría buscarse (siguiente paso)"])
display(falta)
falta.to_csv(PROC / "que_falta.csv", index=False, encoding="utf-8-sig")
reg("falta_no", (falta["¿Está en los datos usados?"] == "No").sum(), n=len(falta), fuente=F)"""),
    ("md", """## 3. Qué revisar antes de decidir con una diferencia de precio

1. **¿Es el mismo artículo?** Misma presentación, marca y canal. La presentación y la marca explican buena parte de la
   diferencia ingenua.
2. **¿Cuántas tiendas hay detrás?** Con una o dos tiendas, el «precio del municipio» es el de esas tiendas.
3. **¿Supera al azar?** Si repartir las tiendas al azar entre municipios da una diferencia parecida, no hay diferencia
   de lugar.
4. **¿La misma cadena cobra distinto?** Si sí, es una decisión de precio por zona; si no, es mezcla de cadenas.
5. **¿Persiste?** Repetir con otra quincena antes de actuar.
6. **¿Qué cuesta llegar ahí y cuánto se vende?** Sin costos, márgenes y volumen, la diferencia no dice si conviene
   actuar."""),
    ("code", """v = entorno.cifras()
display(Markdown(f'''**Conclusión.** Los artefactos más grandes vienen de mezclar presentaciones y marcas bajo un mismo
nombre: en «{casos.producto[0]}», la diferencia ingenua de {casos.ingenua[0]:.0f}% baja a {casos.validada[0]:.0f}% al
comparar lo mismo. De las {len(falta)} piezas de información que harían falta para hablar de oportunidad,
{v["falta_no"]:.0f} no están en los datos públicos usados y {len(falta) - v["falta_no"]:.0f} solo en parte.'''))"""),
])

# --------------------------------------------------------------------------- 05
write("05_visualizaciones.ipynb", [
    head("05", "Visualizaciones, reporte e implicaciones", "¿Cómo se comunica el resultado y qué debe hacer cada audiencia con él?",
         """Genera la gráfica principal (embudo) en tamaño grande y en las versiones para publicar, las gráficas de apoyo,
el README y el reporte HTML con selector de producto. Todo sale de `data/processed/` y de `resultados.json`."""),
    ("code", SETUP.replace("raw = entorno.load_raw()\nd_all = M.prep(raw)\nd = d_all[~d_all.catalogo.isin(M.FUERA_PRINCIPAL)].copy()      # universo principal\n", "")
     + """import graficas as G, reporte as RP, plantillas
v = entorno.cifras()
rd = lambda f, **k: pd.read_csv(PROC / f, encoding="utf-8-sig", **k)
res = rd("embudo.csv")
prod = rd("brecha_producto_paso.csv").set_index("producto")
sob, casos_s = rd("sobrevivientes.csv"), rd("casos_sobreviven.csv")
casos, falta, sens = rd("casos_artefacto.csv"), rd("que_falta.csv"), rd("sensibilidad_embudo.csv")
display(res[["nombre", "brecha_mediana", "ic90_inf", "ic90_sup", "cambio_pp"]].round(1))"""),
    ("md", """## 1. Gráfica principal: el embudo

**Decisión:** barras horizontales en el orden del embudo, con la referencia de azar como línea dorada y el cambio de
cada paso en rojo ▼ (baja) o verde ▲ (sube). Alternativa descartada: un embudo «de embudo» con trapecios, que distorsiona
las magnitudes."""),
    ("code", """G.embudo(res, v, CHARTS / "01_embudo_comparabilidad.png", svg=True)
for fmt in C.SOCIAL:
    G.embudo_social(res, v, fmt, SOCIAL / f"01_embudo_comparabilidad_{fmt}.png")
plt.close("all")"""),
    ("md", "## 2. Gráficas de apoyo"),
    ("code", """G.distribucion(prod, v, CHARTS / "02_distribucion_ingenua_validada.png")
G.artefactos(casos, CHARTS / "03_casos_artefacto.png")
G.sobrevivientes(sob, casos_s, v, CHARTS / "04_casos_sobreviven.png")
G.que_falta(falta, v, CHARTS / "05_que_falta.png")
plt.close("all")
print(sorted(p.name for p in CHARTS.glob("*.png")), sorted(p.name for p in SOCIAL.glob("*.png")))"""),
    ("md", "## 3. README y reporte HTML"),
    ("code", """gallery = [(plantillas.render(gr["titulo"], v), plantillas.render(gr["pie"], v), CHARTS / gr["archivo"]) for gr in CFG["graficas"]]
estructura = (ROOT / "src/estructura.md").read_text(encoding="utf-8")
import readme_md
readme_md.write(CFG, v, ROOT)
RP.build(CFG, v, res, prod, sob, casos, falta, sens, gallery, ROOT / "docs/index.html")
print("README y docs/index.html escritos")"""),
    ("md", "## 4. Qué significa para el negocio"),
    ("code", """for aud, acc in CFG["readme"]["acciones"].items():
    display(Markdown(f"**{aud}**\\n\\n" + "\\n".join(f"- {plantillas.render(a, v)}" for a in acc)))
display(Markdown(f'''**Conclusión.** La diferencia ingenua entre municipios ({v["paso_ingenua"]:.0f}%) baja a {v["validada"]:.1f}% al
comparar lo mismo, casi lo que daría el azar ({v["azar"]:.1f}%). Solo {v["n_sobreviven"]:.0f} de {v["n_articulos"]:,.0f} artículos
tienen una diferencia de municipio que supera la prueba, y aun en ellos faltan costos, márgenes y volumen para hablar
de oportunidad.'''))"""),
])

print("Notebooks generados.")
