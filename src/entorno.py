"""Rutas del análisis, conexión al núcleo y extracto de datos.

Los módulos del núcleo (_profeco_core/src) se importan por nombre: profeco, tablas, pares, unidades, geografia,
estadistica, charts, reporte_base, plantillas. Al publicar, publicar.py los copia a src/ y reemplaza el bloque NUCLEO.
Las cifras clave se registran en data/processed/resultados.json con `registrar` (cifra, intervalo, n, fuente).
"""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
PROC, META = ROOT / "data/processed", ROOT / "data/metadata"
CHARTS, SOCIAL = ROOT / "outputs/charts", ROOT / "outputs/social"
EXTRACTO = PROC / "profeco_extracto.parquet"
RESULTADOS = PROC / "resultados.json"
CONFIG = ROOT / "config.yaml"

# NUCLEO-INICIO
# Publicado: los módulos del núcleo están copiados en src/ (publicar.py) y los datos en
# data/processed/profeco_extracto.parquet. No se depende de _profeco_core.
# NUCLEO-FIN
if EXTRACTO.exists():
    os.environ["PROFECO_EXTRACTO"] = str(EXTRACTO)


def filtro(df):
    """Registros que usa este análisis (define también el extracto que se publica). Ajustar."""
    return df.precio_num > 0


def setup():
    for d in (PROC, META, CHARTS, SOCIAL, ROOT / "docs"):
        d.mkdir(parents=True, exist_ok=True)


def load_raw():
    """Registros del análisis desde el núcleo (o desde el extracto, si el análisis ya se publicó)."""
    import profeco
    import embudo
    return profeco.load(filtro=filtro, columns=embudo.COLS)


def write_manifest(df, extra=None):
    import profeco
    try:
        man = profeco.manifest()
    except FileNotFoundError:
        man = json.loads((META / "manifiesto_insumos.json").read_text(encoding="utf-8"))
    data = {k: man[k] for k in ("archivo_original", "sha256_original", "sha256_parquet", "fecha_inicio", "fecha_fin",
                                "fuente", "nota") if k in man}
    data.update({"registros_analisis": int(len(df)), "modificado": False})
    if extra:
        data.update(extra)
    (META / "manifiesto_insumos.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def registrar(clave, cifra, intervalo=None, n=None, fuente="", nota=""):
    """Cifra clave en data/processed/resultados.json: {clave: {cifra, intervalo, n, fuente, nota}}."""
    import plantillas
    return plantillas.registrar(RESULTADOS, clave, cifra, intervalo, n, fuente, nota)


def cifras():
    import plantillas
    return plantillas.cifras(RESULTADOS)


def config():
    import plantillas
    return plantillas.load_config(CONFIG)


def tabla(nombre, columns=None):
    """Tabla común del núcleo: precio_tienda_sku, tiendas, sku_catalogo o precio_terminacion."""
    import tablas
    return tablas.load(nombre, columns=columns)
