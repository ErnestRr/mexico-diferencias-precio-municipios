"""README con storytelling visual: problema → hallazgo con la gráfica principal → cinco pasos, cada uno con su gráfica y
una tabla o viñetas cortas con deltas (▼ baja, ▲ sube). Lo técnico queda al final, plegado.

Textos en config.yaml (bloques `readme`, `readme_md`) y cifras en data/processed/resultados.json.
"""
from pathlib import Path

import pandas as pd

import charts as C
import plantillas as PL
import embudo as M

URL_PROFECO = "https://qqp.profeco.gob.mx/"


def _usd(t):
    """GitHub lee «$…$» como fórmula: el signo de pesos se escapa."""
    return str(t).replace("$", "\\$")


def _d(v, dec=1, suf=" pp"):
    if abs(v) < 0.05:
        return f"= 0.0{suf}"
    return ("▲ " if v > 0 else "▼ ") + f"{v:+.{dec}f}{suf}".replace("-", "−")


def _c(v, dec=1, suf=" pp"):
    """Delta con color por signo en GitHub: verde ▲ positivo, rojo ▼ negativo.

    Solo la flecha y el número van en la fórmula de color. La unidad (% o pp) va fuera: GitHub convierte «\\%» en
    «%», que en la fórmula abre un comentario y rompe la llave de cierre. Tampoco se usan «\\ » ni «\\,»."""
    if abs(v) < 0.05:
        return "= 0.0" + suf
    col, sym = (C.GREEN_T, "\\blacktriangle") if v > 0 else (C.RED_T, "\\blacktriangledown")
    return "$\\color{" + col + "}{" + sym + "~" + f"{v:+.{dec}f}" + "}$" + suf


def _tabla(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def build(cfg, v, root):
    root = Path(root)
    proc = root / "data/processed"
    rd = lambda f: pd.read_csv(proc / f, encoding="utf-8-sig")
    res, prod, casos, sob = rd("embudo.csv"), rd("brecha_producto_paso.csv"), rd("casos_artefacto.csv"), rd("sobrevivientes.csv")
    v = dict(v)
    x = prod.dropna(subset=["ingenua", "extremos"])
    v["pct_val_30"] = (x.extremos > 30).mean() * 100
    v["delta_30"] = v["pct_val_30"] - (x.ingenua > 30).mean() * 100
    v["delta_pp"] = v["validada"] - v["paso_ingenua"]
    cam = dict(zip(res.paso, res.cambio_pp))
    color = {"c_delta_30": _c(v["delta_30"], 0), "c_delta_pp": _c(v["delta_pp"]),
             "c_pres": _c(cam["presentacion"]), "c_tiendas": _c(cam["tiendas"]),
             "c_sobre_azar": _c(v["validada"] - v["azar"]), "c_desaparece": _c(-v["desaparece_pct"], 0, "%"),
             "c_cad_sob": _c(v["cadena_sobreviven"], 0, "%"), "c_cad_no": _c(v["cadena_no_sobreviven"], 1, "%")}
    for k in color:
        v[k] = f"@@{k}@@"

    def R(t):
        out = _usd(PL.render(t, v))
        for k, m in color.items():
            out = out.replace(f"@@{k}@@", m)
        return out
    r, md = cfg["readme"], cfg["readme_md"]

    tablas = {
        "embudo": _tabla(["Paso", "Diferencia típica", "Cambio"],
                         [[f"{i}. {t.nombre}", f"**{t.brecha_mediana:.1f}%**", "—" if i == 0 else _c(t.cambio_pp)]
                          for i, t in enumerate(res.itertuples())] + [["Referencia: azar", f"{v['azar']:.1f}%", ""]]),
        "artefactos": _tabla(["Qué lo producía", "Producto", "Antes", "Después", "Cambio"],
                             [[c.tipo, c.producto, f"{c.antes:.0f}%", f"{c.despues:.0f}%", _c(c.despues - c.antes, 0)]
                              for c in casos.itertuples()]),
        "sobreviven": _tabla(["Artículo", "Giro", "Diferencia", "IC90", "Barato → caro típico"],
                             [[c.etiqueta, M.giro_corto(c.giro), _c(c.brecha_pct, 0, "%"), f"{c.ic90_inf:.0f}–{c.ic90_sup:.0f}%",
                               _usd(f"{c.mun_barato} {C.money(c.precio_barato)} → {c.mun_caro} {C.money(c.precio_caro)}")]
                              for c in sob[sob.relevante].sort_values("p_valor").head(8).itertuples()]),
    }

    L = [f"# {cfg['titulo']}", "",
         f"**Objetivo.** {R(cfg['objetivo'])}", "",
         f"**{R(cfg['pregunta'])}**", "",
         R(r["enlace_reporte"]), "",
         "## El problema", "", R(md["problema"]), "",
         "## El hallazgo", "", R(md["hallazgo"]), "",
         f"![{r['alt_grafica']}]({r['grafica_principal']})", "",
         _tabla(["Indicador", "Cifra"], [
             ["Diferencia típica a lo bruto", f"**{v['paso_ingenua']:.0f}%**"],
             ["Al comparar el mismo artículo", f"**{v['validada']:.1f}%** ({color['c_delta_pp']})"],
             ["Lo que daría el azar con las mismas tiendas", f"{v['azar']:.1f}%"],
             ["Parte de la diferencia ingenua que desaparece", f"**{v['desaparece_pct']:.0f}%** " + r"$\color{" + C.RED_T + r"}{\blacktriangledown}$"],
             ["Artículos con diferencia relevante", f"{v['n_relevantes']:.0f} de {v['n_articulos']:,.0f}"]]), "",
         "*Brecha P90/P10 = cuánto más cuesta un producto en el municipio caro típico que en el barato típico. "
         "IC90 = rango probable. Verde ▲ = sube o es positivo; rojo ▼ = baja o es negativo.*", ""]

    for p in md["pasos"]:
        L += [f"## {p['titulo']}", ""]
        if p.get("grafica"):
            L += [f"![{p.get('alt', '')}](outputs/charts/{p['grafica']})", ""]
        if p.get("tabla"):
            L += [tablas[p["tabla"]], ""]
        L += [f"- {R(t)}" for t in p.get("puntos", [])] + [""]

    L += ["## Lo que no resultó sólido", ""] + [f"- {R(t)}" for t in md["no_solido"]] + [""]
    L += ["## Qué hacer con esto", "", R(r["alcance"]), ""]
    L += [_tabla(["Para", "Acción"], [[f"**{a}**", R(t)] for a, t in md["acciones"].items()]), ""]
    L += ["## Cómo se hizo", ""] + [f"- {R(t)}" for t in md["como_se_hizo"]] + [""]
    L += ["## Limitaciones", ""] + [f"- {R(t)}" for t in md["limitaciones"]] + [""]
    L += ["## Método detallado", "", "<details>", "<summary>Ver tablas de sensibilidad y detalle por notebook</summary>", "",
          R(r["metodo"]), "", "</details>", ""]
    L += ["## Fuentes", "",
          "Gráficas y cifras: elaboración propia con datos de PROFECO. Color por signo en las gráficas: verde ▲ = valor "
          "positivo; rojo ▼ = negativo; dorado = referencia.", "",
          f"- **PROFECO**, Quién es Quién en los Precios: archivo `08-2026_Q2.csv` (16–31 ago 2026). **URL oficial del "
          f"programa:** {URL_PROFECO}", ""]
    L += ["## Estructura y reproducción", "", "<details>", "<summary>Ver estructura y pasos</summary>", "",
          (root / "src/estructura.md").read_text(encoding="utf-8"), "", "</details>", ""]
    L += ["---", "", f"**Autor:** {cfg.get('firma', C.FIRMA)}", ""]
    return "\n".join(L)


def write(cfg, v, root):
    path = Path(root) / "README.md"
    path.write_text(build(cfg, v, root), encoding="utf-8")
    return path
