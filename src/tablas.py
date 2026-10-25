# Copiado de _profeco_core/src/tablas.py por publicar.py; no editar aquí.
"""Tablas comunes de la serie, construidas una vez desde el Parquet base (data/profeco_2026_08_q2.parquet).

- precio_tienda_sku: precio representativo por tienda y SKU en la quincena (mediana de sus observaciones).
- tiendas: una fila por tienda, con cadena, formato, grupo, giro, municipio, región y calidad de coordenadas.
- sku_catalogo: SKU con categoría, marca, tamaño y unidad normalizados, y empresa propietaria verificada.
- precio_terminacion: cada observación de precio con centavos, último dígito y tipo de terminación.

Uso: python src/tablas.py  (escribe los Parquet en data/ y los agrega al manifiesto).
"""
from pathlib import Path
import json
import re

import numpy as np
import pandas as pd

import profeco

DATA = profeco.CORE / "data"
TABLAS = {k: DATA / f"{k}.parquet" for k in ("precio_tienda_sku", "tiendas", "sku_catalogo", "precio_terminacion")}

# Corporativo de cada cadena (formatos del mismo grupo). Fuente: nombres de cadena de PROFECO; los formatos de un
# mismo corporativo se agrupan como en el análisis de marca propia.
GRUPO = {
    "Wal-mart": "Walmart de México", "Wal-mart Express": "Walmart de México", "Bodega Aurrera": "Walmart de México",
    "Bodega Aurrera Express": "Walmart de México",
    "Hipermercado Soriana": "Soriana", "Mega Soriana": "Soriana", "Mercado Soriana": "Soriana",
    "Soriana Super": "Soriana", "Soriana Express": "Soriana",
    "Chedraui": "Chedraui", "Super Chedraui": "Chedraui", "Chedraui Selecto": "Chedraui",
    "La Comer": "La Comer", "Fresko la Comer": "La Comer", "Sumesa": "La Comer", "City Market": "La Comer",
    "Ley": "Ley", "Ley Express": "Ley", "Super Aki": "Super Aki", "Super Aki Xtra": "Super Aki",
    "H.e.b.": "HEB", "Superissste": "Superissste", "S Mart": "S Mart",
    "Farmacias de Similares": "Farmacias Similares", "Farmacias Similares": "Farmacias Similares",
}
# Nombre de formato para mostrar (los formatos son las cadenas de PROFECO con nombre corregido).
FORMATO = {
    "Wal-mart": "Walmart", "Wal-mart Express": "Walmart Express", "Bodega Aurrera": "Bodega Aurrerá",
    "Bodega Aurrera Express": "Bodega Aurrerá Express", "H.e.b.": "HEB", "Fresko la Comer": "Fresko",
    "Farmacias de Similares": "Farmacias Similares", "Sanborn S Hnos.": "Sanborns",
}
# Regiones de Banco de México (Reporte sobre las Economías Regionales).
REGION = {
    **dict.fromkeys(["Baja California", "Chihuahua", "Coahuila", "Nuevo León", "Sonora", "Tamaulipas"], "Norte"),
    **dict.fromkeys(["Aguascalientes", "Baja California Sur", "Colima", "Durango", "Jalisco", "Michoacán", "Nayarit",
                     "San Luis Potosí", "Sinaloa", "Zacatecas"], "Centro Norte"),
    **dict.fromkeys(["Ciudad de México", "Estado de México", "Guanajuato", "Hidalgo", "Morelos", "Puebla", "Querétaro",
                     "Tlaxcala"], "Centro"),
    **dict.fromkeys(["Campeche", "Chiapas", "Guerrero", "Oaxaca", "Quintana Roo", "Tabasco", "Veracruz", "Yucatán"],
                    "Sur"),
}
# Empresa propietaria: solo marcas que usan los análisis 6–12 y verificadas en una fuente oficial de la empresa.
# Si no se pudo verificar, no se agrega (queda vacía).
PROPIETARIA = {
    "Coca Cola": ("The Coca-Cola Company",
                  "Form 10-K 2025, Item 1: «We own and market numerous valuable beverage brands, including… Coca-Cola, "
                  "Diet Coke/Coca-Cola Light, Coca-Cola Zero Sugar»",
                  "https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm"),
    "Pepsi": ("PepsiCo, Inc.", "Form 10-K 2025: «We own numerous valuable trademarks… including… Pepsi, Pepsi Black…»",
              "https://www.sec.gov/Archives/edgar/data/77476/000007747626000007/pep-20251227.htm"),
    "Sabritas": ("PepsiCo, Inc.", "Form 10-K 2025: «We own numerous valuable trademarks… including… Sabritas…»",
                 "https://www.sec.gov/Archives/edgar/data/77476/000007747626000007/pep-20251227.htm"),
    "Gamesa": ("PepsiCo, Inc.", "Form 10-K 2025: «We own numerous valuable trademarks… including… Gamesa…»",
               "https://www.sec.gov/Archives/edgar/data/77476/000007747626000007/pep-20251227.htm"),
    "Huggies": ("Kimberly-Clark de México",
                "Informe Anual 2025: «Entre sus principales marcas se encuentran: Huggies®, KleenBebé®…» (KCM comercializa "
                "la marca en México; la relación tecnológica es con Kimberly-Clark Corporation)",
                "https://www.kimberly-clark.com.mx/data/2026/KCMIA2025ESP.pdf"),
    "Kleen Bebé": ("Kimberly-Clark de México", "Informe Anual 2025: «Entre sus principales marcas se encuentran: Huggies®, "
                   "KleenBebé®…»", "https://www.kimberly-clark.com.mx/data/2026/KCMIA2025ESP.pdf"),
    "Kleen Bebe": ("Kimberly-Clark de México", "Informe Anual 2025 (misma marca que «Kleen Bebé», escrita sin acento)",
                   "https://www.kimberly-clark.com.mx/data/2026/KCMIA2025ESP.pdf"),
    "Bimbo": ("Grupo Bimbo", "Sitio corporativo: «El portafolio de Grupo Bimbo en México incluye más de 19 marcas, entre "
              "ellas: Bimbo, Marinela»", "https://www.grupobimbo.com/en/node/2148"),
    "Marinela": ("Grupo Bimbo", "Sitio corporativo: «El portafolio de Grupo Bimbo en México incluye más de 19 marcas, "
                 "entre ellas: Bimbo, Marinela»", "https://www.grupobimbo.com/en/node/2148"),
}
FECHA_VERIFICACION = "2026-10-21"
_PIEZAS = re.compile(r"(\d+)\s*(?:piezas?|pzas?|rollos?|tabletas?|c[aá]psulas?|sobres?|toallitas?)\b", re.I)


def precio_tienda_sku(base):
    """Mediana de las observaciones de cada tienda y SKU en la quincena (decisión del análisis 2: la mayoría de los
    pares tiene 1–2 observaciones y casi siempre el mismo precio; la mediana ignora la promoción o el error aislado)."""
    x = base[base.precio_num > 0]
    g = x.groupby(["establecimiento_id", "sku_id"], observed=True)
    out = g.agg(precio=("precio_num", "median"), observaciones=("precio_num", "size"),
                precios_distintos=("precio_num", "nunique"), precio_min=("precio_num", "min"),
                precio_max=("precio_num", "max"), dias=("fecha", "nunique"), fecha_min=("fecha", "min"),
                fecha_max=("fecha", "max")).reset_index()
    cant = base.drop_duplicates("sku_id").set_index("sku_id").cantidad_base
    out["precio_unidad"] = out.precio / out.sku_id.map(cant)
    return out


def tiendas(base):
    cols = ["establecimiento_id", "cadena_comercial", "nombre_comercial", "giro", "estado", "municipio", "municipio_id",
            "direccion", "lat", "lon"]
    st = base.drop_duplicates("establecimiento_id")[cols].copy()
    for c in cols[1:8]:
        st[c] = st[c].astype(str)
    st["formato"] = st.cadena_comercial.map(FORMATO).fillna(st.cadena_comercial)
    st["grupo"] = st.cadena_comercial.map(GRUPO).fillna(st.cadena_comercial)
    st["region"] = st.estado.map(REGION)
    # Calidad de coordenadas: dentro de México, la misma en todas las observaciones de la tienda, no compartida con
    # otra tienda (señal de geocodificación al centro de la ciudad) y a menos de 30 km de la mediana de su municipio.
    var = base.groupby("establecimiento_id", observed=True)[["lat", "lon"]].std().max(axis=1).reindex(st.establecimiento_id)
    in_mx = st.lat.between(14.0, 33.0) & st.lon.between(-118.5, -86.5)
    shared = st.groupby([st.lat.round(5), st.lon.round(5)]).establecimiento_id.transform("size") > 1
    med = st[in_mx].groupby("municipio_id")[["lat", "lon"]].median()
    mlat, mlon = st.municipio_id.map(med.lat), st.municipio_id.map(med.lon)
    dist = np.sqrt(((st.lat - mlat) * 111.0) ** 2 + ((st.lon - mlon) * 111.0 * np.cos(np.radians(st.lat))) ** 2)
    motivo = np.select([st.lat.isna() | st.lon.isna(), ~in_mx, var.to_numpy() > 0.001, shared, dist > 30],
                       ["sin coordenadas", "fuera de México", "cambia entre observaciones", "compartida con otra tienda",
                        "a más de 30 km de su municipio"], "")
    st["coord_ok"] = motivo == ""
    st["coord_motivo"] = motivo
    return st.reset_index(drop=True)


def sku_catalogo(base):
    cols = ["sku_id", "producto", "presentacion", "marca", "categoria", "catalogo", "cantidad_base", "unidad_base"]
    cat = base.drop_duplicates("sku_id")[cols].copy()
    for c in cols[1:6] + ["unidad_base"]:
        cat[c] = cat[c].astype(str).replace({"None": np.nan, "nan": np.nan})
    cat["familia"] = cat.marca.str.split(".").str[0].str.strip()
    pres = cat.presentacion.fillna("")
    amb = pres.str.contains(r"\d+\s*[óo]\s*\d+", regex=True)
    pz = pres.str.extract(_PIEZAS)[0].astype(float)
    cat["piezas"] = pz.where(~amb)
    cat["presentacion_ambigua"] = amb
    own = cat.familia.map(lambda f: PROPIETARIA.get(f, (None, None, None)))
    cat["empresa_propietaria"] = [o[0] for o in own]
    cat["fuente_propietaria"] = [o[1] for o in own]
    cat["url_fuente_propietaria"] = [o[2] for o in own]
    cat["fecha_verificacion"] = np.where(cat.empresa_propietaria.notna(), FECHA_VERIFICACION, None)
    return cat.sort_values("sku_id").reset_index(drop=True)


def precio_terminacion(base):
    x = base[base.precio_num > 0].reset_index().rename(columns={"index": "obs_id"})
    cent = np.round(x.precio_num * 100).astype("int64") % 100
    out = pd.DataFrame({"obs_id": x.obs_id.astype("int32"), "establecimiento_id": x.establecimiento_id,
                        "sku_id": x.sku_id, "fecha": x.fecha, "precio": x.precio_num, "centavos": cent.astype("int16"),
                        "ultimo_digito": (np.floor(x.precio_num).astype("int64") % 10).astype("int8")})
    out["terminacion"] = pd.Categorical(np.select([cent == 0, cent == 50, cent == 90, cent == 99],
                                                  ["cerrado", ".50", ".90", ".99"], "otro"),
                                        categories=["cerrado", ".50", ".90", ".99", "otro"])
    return out


DESCRIPCION = {
    "precio_tienda_sku": "Precio representativo por tienda y SKU: mediana de sus observaciones en la quincena; incluye "
                         "observaciones, precios distintos, mínimo, máximo, días y precio por unidad base.",
    "tiendas": "Una fila por tienda: cadena, formato, grupo corporativo, giro, municipio, región (Banxico) y coordenadas "
               "con bandera de calidad (coord_ok, coord_motivo).",
    "sku_catalogo": "Un SKU (producto + presentación + marca literal) por fila: categoría, familia de marca, cantidad y "
                    "unidad base, piezas por paquete y empresa propietaria verificada con fuente oficial (vacía si no se "
                    "verificó).",
    "precio_terminacion": "Cada observación con precio > 0: centavos, último dígito de los pesos y terminación "
                          "(cerrado, .50, .90, .99, otro).",
}


def build():
    base = pd.read_parquet(profeco.PARQUET)
    out = {"precio_tienda_sku": precio_tienda_sku(base), "tiendas": tiendas(base),
           "sku_catalogo": sku_catalogo(base), "precio_terminacion": precio_terminacion(base)}
    man = json.loads(profeco.MANIFEST.read_text(encoding="utf-8"))
    man["tablas"] = {}
    for k, df in out.items():
        df.to_parquet(TABLAS[k], index=False, compression="zstd")
        man["tablas"][k] = {"archivo": TABLAS[k].name, "filas": int(len(df)), "columnas": list(df.columns),
                            "sha256": profeco.sha256(TABLAS[k]), "descripcion": DESCRIPCION[k]}
    profeco.MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {k: len(v) for k, v in out.items()}


def _local(nombre):
    """Copia local de la tabla en un análisis publicado (data/processed/tablas/<nombre>.parquet)."""
    import os
    env = os.environ.get("PROFECO_TABLAS")
    cands = [Path(env) / f"{nombre}.parquet"] if env else []
    here = Path.cwd()
    cands += [d / "data/processed/tablas" / f"{nombre}.parquet" for d in [here, *here.parents][:3]]
    return next((c for c in cands if c.exists()), None)


def load(nombre, columns=None):
    """Tabla común; en un análisis publicado se lee su copia local, sin depender del núcleo."""
    src = _local(nombre) or TABLAS[nombre]
    return pd.read_parquet(src, columns=columns)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    print(build())
