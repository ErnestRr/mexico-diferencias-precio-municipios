```
mexico-diferencias-precio-municipios/
├── notebooks/        00 datos y decisiones · 01 comparación ingenua · 02 embudo de comparabilidad
│                     03 diferencias que sobreviven · 04 artefactos y lo que falta · 05 visualizaciones
├── config.yaml       objetivo, preguntas y textos del README y del reporte
├── src/              entorno.py, embudo.py (pasos, brechas, bootstrap, prueba y azar), graficas.py, reporte.py
├── data/processed/   embudo, brecha por producto y paso, artículos probados, casos y resultados.json (CSV)
├── data/metadata/    parametros.json, manifiesto_insumos.json
├── outputs/charts/   gráficas PNG (la principal también en SVG)
├── outputs/social/   versiones de 1280×720 y 1080×1350
├── docs/index.html   reporte interactivo autocontenido con selector de producto
├── build_notebooks.py
└── verify_project.py
```

```powershell
python -m pip install -r requirements.txt
python build_notebooks.py
$env:OMP_NUM_THREADS = 1; $env:OPENBLAS_NUM_THREADS = 1; $env:MKL_NUM_THREADS = 1
foreach ($n in Get-ChildItem notebooks/0*.ipynb) {
  python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 $n.FullName
}
python verify_project.py
```

`verify_project.py` recalcula la comparación ingenua y la validada solo con pandas y numpy a partir de los precios
originales y comprueba que coinciden con este README.
