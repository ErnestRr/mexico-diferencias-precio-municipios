# Copiado de _profeco_core/src/profeco.py por publicar.py; no editar aquí.
"""Lectura y limpieza del archivo de PROFECO (Quién es Quién en los Precios, 08-2026_Q2.csv).

El CSV original se lee una sola vez y se guarda en Parquet con tipos, fecha, precio numérico y claves.
Las columnas originales se conservan con su texto literal; no se elimina ninguna fila.

Columnas agregadas:
- precio_num, fecha, lat, lon: tipos numéricos y fecha (NaN si el texto no es válido);
- establecimiento_id: estado + municipio + cadena + nombre comercial + dirección (mismo orden que los proyectos
  anteriores, así que los identificadores coinciden);
- sku_id: producto + presentación + marca con el texto literal idéntico;
- municipio_id: «estado | municipio»;
- cantidad_base, unidad_base: cantidad normalizada de la presentación (kg, l o pieza; ver unidades.py).

Uso en un análisis:
    import profeco
    df = profeco.load()                                   # todo el archivo
    df = profeco.load(filtro=lambda d: d.catalogo == "Medicamentos")
Al publicar (publicar.py), el análisis guarda su extracto en data/processed/profeco_extracto.parquet y
`load()` lo usa primero, sin depender del núcleo.
"""
from pathlib import Path
import hashlib
import json
import os
import unicodedata

import numpy as np
import pandas as pd

CORE = Path(__file__).resolve().parents[1]
PARQUET = CORE / "data/profeco_2026_08_q2.parquet"
MANIFEST = CORE / "data/manifiesto.json"
EXTRACTO = "data/processed/profeco_extracto.parquet"
ARCHIVO = "08-2026_Q2.csv"
PERIODO = "16–31 ago 2026"
FUENTE = "PROFECO, Quién es Quién en los Precios"
URL_OFICIAL = "https://qqp.profeco.gob.mx/"
NOTA_URL = f"URL oficial del programa Quién es Quién en los Precios: {URL_OFICIAL}"
URL_PENDIENTE = NOTA_URL  # nombre anterior, para módulos copiados que aún lo importan

EXPECTED = [
    "producto", "presentacion", "marca", "categoria", "catalogo", "precio",
    "fecha_registro", "cadena_comercial", "giro", "nombre_comercial",
    "direccion", "estado", "municipio", "latitud", "longitud",
]
STORE = ["estado", "municipio", "cadena_comercial", "nombre_comercial", "direccion"]
ITEM = ["producto", "presentacion", "marca"]
CANAL_SUPER = "Supermercado / Tienda de Autoservicio"
# Conteos del archivo original: la prueba del núcleo los exige.
CONTEOS = {"registros": 657_602, "tiendas": 1_857, "municipios": 72}


def source_path():
    """Ruta del CSV original: variable PROFECO_CSV, data/raw/ del núcleo o carpeta 20octubre26."""
    cands = [os.environ.get("PROFECO_CSV"), CORE / "data/raw" / ARCHIVO, CORE.parent / ARCHIVO]
    for c in cands:
        if c and Path(c).exists():
            return Path(c)
    raise FileNotFoundError(f"No se encontró {ARCHIVO}: colócalo en {CORE.parent} o define PROFECO_CSV.")


def normalized_text(value):
    """Minúsculas, sin acentos y con espacios simples (solo para comparar textos, nunca para guardar)."""
    text = " ".join(str(value).strip().casefold().split())
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def read_csv(path=None):
    """CSV original como texto. «S/M», «NA» y similares se conservan como texto, no como nulos."""
    path = Path(path) if path else source_path()
    df = pd.read_csv(path, dtype="string", encoding="utf-8-sig", keep_default_na=False)
    if list(df.columns) != EXPECTED:
        raise ValueError(f"Esquema inesperado: {df.columns.tolist()}")
    if df.empty:
        raise ValueError("El CSV está vacío.")
    return df


def prepare(df):
    """Agrega tipos, fecha y claves; no elimina filas ni modifica las columnas originales."""
    from unidades import parse_quantity

    out = df.copy()
    out["precio_num"] = pd.to_numeric(out.precio, errors="coerce").astype(float)
    out["fecha"] = pd.to_datetime(out.fecha_registro, format="%Y/%m/%d", errors="coerce")
    out["lat"] = pd.to_numeric(out.latitud, errors="coerce").astype(float)
    out["lon"] = pd.to_numeric(out.longitud, errors="coerce").astype(float)
    out["establecimiento_id"] = pd.factorize(pd.MultiIndex.from_frame(out[STORE]))[0].astype("int32")
    out["sku_id"] = pd.factorize(pd.MultiIndex.from_frame(out[ITEM]))[0].astype("int32")
    out["municipio_id"] = out.estado + " | " + out.municipio
    pres = pd.Series(out.presentacion.unique())
    parsed = pd.DataFrame(pres.map(parse_quantity).tolist(), columns=["cantidad_base", "unidad_base"], index=pres)
    out = out.join(parsed, on="presentacion")
    # Texto repetido como categoría: el Parquet pesa una fracción del CSV.
    for c in EXPECTED + ["municipio_id", "unidad_base"]:
        if c not in ("precio", "latitud", "longitud", "fecha_registro"):
            out[c] = out[c].astype("category")
    return out


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def build(path=None):
    """Lee el CSV una vez, escribe el Parquet y el manifiesto con SHA-256 de ambos."""
    src = Path(path) if path else source_path()
    df = prepare(read_csv(src))
    PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PARQUET, index=False, compression="zstd")
    man = {
        "archivo_original": src.name, "ruta_original": str(src), "sha256_original": sha256(src),
        "bytes_original": src.stat().st_size, "parquet": PARQUET.name, "sha256_parquet": sha256(PARQUET),
        "bytes_parquet": PARQUET.stat().st_size, "registros": int(len(df)),
        "tiendas": int(df.establecimiento_id.nunique()), "municipios": int(df.municipio_id.nunique()),
        "skus": int(df.sku_id.nunique()), "fecha_inicio": str(df.fecha.min().date()),
        "fecha_fin": str(df.fecha.max().date()), "fuente": FUENTE, "nota": NOTA_URL,
        "modificado": False,
    }
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return man


def _find_extract():
    """Extracto local de un análisis publicado (busca data/processed/ hacia arriba desde el directorio actual)."""
    env = os.environ.get("PROFECO_EXTRACTO")
    if env and Path(env).exists():
        return Path(env)
    here = Path.cwd()
    for d in [here, *here.parents][:3]:
        p = d / EXTRACTO
        if p.exists():
            return p
    return None


def load(filtro=None, columns=None, prefer_extract=True):
    """Archivo preparado. Usa el extracto del análisis si existe; si no, el Parquet del núcleo."""
    src = _find_extract() if prefer_extract else None
    if src is None:
        if not PARQUET.exists():
            raise FileNotFoundError(f"Falta {PARQUET}: ejecutar `python {CORE / 'src/profeco.py'}`.")
        src = PARQUET
    df = pd.read_parquet(src, columns=columns)
    if filtro is not None:
        df = df[filtro(df)]
    for c in df.select_dtypes("category").columns:
        df[c] = df[c].cat.remove_unused_categories()
    return df.reset_index(drop=True)


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    print(json.dumps(build(), ensure_ascii=False, indent=2))
