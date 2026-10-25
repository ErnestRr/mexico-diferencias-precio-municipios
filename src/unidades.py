# Copiado de _profeco_core/src/unidades.py por publicar.py; no editar aquí.
"""Normalización de unidades de las presentaciones PROFECO (tomado de mexico-costo-canasta/src/cleaning.py).

Regla: solo se normaliza cuando la presentación tiene una cantidad inequívoca. Las ambiguas (dos cantidades,
rangos como «800 Ó 880 Gr.» o sin cantidad) devuelven NaN y no se usan para precio por unidad.
"""
import re

import numpy as np
import pandas as pd

_QTY = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|gr|g|lt|l|ml)\.?(?![a-z])", re.IGNORECASE)
_PIEZAS = re.compile(r"C/(\d+)", re.IGNORECASE)
_A_BASE = {"kg": ("kg", 1.0), "gr": ("kg", 0.001), "g": ("kg", 0.001),
           "lt": ("l", 1.0), "l": ("l", 1.0), "ml": ("l", 0.001)}


def parse_quantity(presentacion):
    """(cantidad, unidad base) con unidad en kg, l o pieza; (nan, None) si la presentación es ambigua."""
    text = str(presentacion)
    if re.search(r"\d\s*[óo]\s*\d", text, re.IGNORECASE):
        return np.nan, None
    pieces = _PIEZAS.findall(text)
    if len(pieces) == 1:
        return float(pieces[0]), "pieza"
    found = _QTY.findall(text)
    if len(found) == 1:
        value, unit = found[0]
        base, factor = _A_BASE[unit.lower()]
        return float(value) * factor, base
    if text.strip().lower() == "pieza":
        return 1.0, "pieza"
    return np.nan, None


def price_per_unit(df, price="precio_num"):
    """Precio por kg, litro o pieza. NaN cuando la presentación no se pudo normalizar."""
    out = df[price] / df.cantidad_base
    return out.where(df.cantidad_base > 0)


def unit_label(unidad):
    return {"kg": "por kg", "l": "por litro", "pieza": "por pieza"}.get(unidad, "")
