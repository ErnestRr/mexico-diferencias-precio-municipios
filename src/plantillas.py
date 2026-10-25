"""Plantillas por configuración: cada análisis describe sus textos en `config.yaml` y sus cifras en
`data/processed/resultados.json`; de ahí salen los encabezados de los notebooks, el README y el reporte HTML.

Los textos de config.yaml pueden llevar marcadores {clave} o {clave:.0f} que se llenan con la cifra registrada en
resultados.json (`registrar`). Así el README, el HTML y la verificación usan exactamente los mismos números.

El diseño visual es el de reporte_base (el mismo de los análisis 3 a 5) y el README sigue el orden fijo de la serie (objetivo, hallazgo, apoyo, negocio, método).
"""
from pathlib import Path
import json
import string

import yaml

import charts as C


# --------------------------------------------------------------------------- configuración y resultados
def load_config(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg.setdefault("firma", C.FIRMA)
    return cfg


def registrar(path, clave, cifra, intervalo=None, n=None, fuente="", nota=""):
    """Guarda una cifra clave en resultados.json: {clave: {cifra, intervalo, n, fuente, nota}}."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    to_f = lambda v: None if v is None else (float(v) if isinstance(v, (int, float)) or hasattr(v, "item") else v)
    data[clave] = {"cifra": to_f(cifra), "intervalo": None if intervalo is None else [to_f(v) for v in intervalo],
                   "n": None if n is None else int(n), "fuente": fuente, "nota": nota}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return data


def cifras(path):
    """{clave: cifra} más {clave_inf, clave_sup, clave_n} para usar en los marcadores de texto."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    out = {}
    for k, v in data.items():
        if isinstance(v, dict) and "cifra" in v:
            out[k] = v["cifra"]
            if v.get("intervalo"):
                out[f"{k}_inf"], out[f"{k}_sup"] = v["intervalo"]
            if v.get("n") is not None:
                out[f"{k}_n"] = v["n"]
        else:
            out[k] = v
    return out


class _Faltante(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class _Fmt(string.Formatter):
    """Formato con signo menos tipográfico (−) para cifras negativas."""
    def format_field(self, value, spec):
        txt = super().format_field(value, spec)
        return txt.replace("-", "−") if isinstance(value, (int, float)) else txt


def render(texto, valores):
    if texto is None:
        return ""
    if isinstance(texto, list):
        return [render(t, valores) for t in texto]
    try:
        return _Fmt().vformat(str(texto), (), _Faltante(valores))
    except (ValueError, KeyError):
        return str(texto)


# --------------------------------------------------------------------------- notebooks
def encabezado(cfg, numero, titulo, pregunta_notebook, porque=""):
    """Celda markdown de apertura de un notebook: objetivo del análisis y pregunta del notebook."""
    txt = f"# {numero:02d} · {titulo}\n\n**Objetivo:** {cfg.get('objetivo', '')}\n\n**Pregunta:** {pregunta_notebook}"
    if porque:
        txt += f"\n\n{porque}"
    return ("md", txt)


# --------------------------------------------------------------------------- README
def readme(cfg, valores, estructura=None):
    """README en el orden fijo de la serie con los textos de config.yaml y las cifras de resultados.json."""
    r = cfg.get("readme", {})
    v = valores
    lines = [f"# {cfg.get('titulo', '')}", "", f"**Objetivo.** {render(cfg.get('objetivo'), v)}", "",
             f"**{render(cfg.get('pregunta'), v)}**", ""]
    if r.get("enlace_reporte"):
        lines += [render(r["enlace_reporte"], v), ""]
    lines += ["## El hallazgo principal", "",
             render(r.get("hallazgo_principal", ""), v), ""]
    if r.get("grafica_principal"):
        lines += [f"![{r.get('alt_grafica', 'Gráfica principal')}]({r['grafica_principal']})", ""]
    if r.get("nota_principal"):
        lines += [render(r["nota_principal"], v), ""]
    lines += ["## Tres hallazgos de apoyo", ""]
    lines += [f"{i}. {render(h, v)}" for i, h in enumerate(r.get("hallazgos_apoyo", []), 1)]
    lines += ["", f"**Lo que no resultó sólido.** {render(r.get('no_solido', ''), v)}", "",
              "## Qué significa para el negocio y qué hacer", "",
              render(r.get("alcance", "Aplica a las tiendas que monitorea PROFECO, no a todo el mercado."), v), ""]
    for aud, acciones in (r.get("acciones") or {}).items():
        lines += [f"**{aud}**"] + [f"- {render(a, v)}" for a in acciones] + [""]
    lines += ["## Cómo se hizo (breve)", ""] + [f"- {render(x, v)}" for x in r.get("como_se_hizo", [])] + [""]
    lines += ["## Limitaciones", ""] + [f"- {render(x, v)}" for x in r.get("limitaciones", [])] + [""]
    if r.get("metodo"):
        lines += ["## Método", "", render(r["metodo"], v), ""]
    lines += ["## Fuentes", "", "Todas las gráficas y cifras son **elaboración propia con datos de PROFECO**. Convención "
              "de color por signo: verde = valor positivo (▲); rojo = valor negativo (▼). Dorado marca referencias.", ""]
    lines += [f"- {render(x, v)}" for x in r.get("fuentes", [])]
    lines += ["- **PROFECO**, Quién es Quién en los Precios: archivo `08-2026_Q2.csv` (16–31 ago 2026). **URL oficial del "
              "programa:** https://qqp.profeco.gob.mx/", ""]
    if estructura:
        lines += ["## Estructura y reproducción", "", estructura, ""]
    if r.get("autor"):
        lines += ["---", "", f"**Autor:** {cfg.get('firma', C.FIRMA)}", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- reporte HTML
def pagina(cfg, valores, secciones, galeria, extra_js=""):
    """Reporte HTML con el diseño de reporte_base; textos de config.yaml (bloque `reporte`)."""
    import reporte_base as RB
    rep = cfg.get("reporte", {})
    v = valores
    stats = [(render(s.get("valor"), v), s.get("clase", ""), render(s.get("texto"), v)) for s in rep.get("stats", [])]
    acciones = [(aud, render(" ".join(a), v)) for aud, a in (cfg.get("readme", {}).get("acciones") or {}).items()]
    return RB.page(titulo=cfg.get("titulo", ""), descripcion=render(rep.get("descripcion", ""), v),
                   objetivo=render(cfg.get("objetivo", ""), v), h1=render(rep.get("h1", ""), v),
                   intro=render(rep.get("intro", ""), v), stats=stats, secciones=secciones, acciones=acciones,
                   galeria=galeria, metodo=render(rep.get("metodo", []), v), extra_js=extra_js)
