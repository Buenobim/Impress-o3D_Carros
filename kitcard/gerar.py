# -*- coding: utf-8 -*-
"""
Gera um carro:  blender -b --factory-startup -P kitcard/gerar.py -- <pasta_do_carro>
Ex.:            blender -b --factory-startup -P kitcard/gerar.py -- gol_1980
"""
import importlib, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not args:
    raise SystemExit("informe o carro: ... -P kitcard/gerar.py -- <pasta em carros/>")
from kitcard import nucleo
mod = importlib.import_module(f"carros.{args[0]}.modelo")
nucleo.gerar(mod)
