#!/usr/bin/env python3
"""
Conferidor de Loterias Caixa
  python main.py        → interface gráfica (padrão)
  python main.py --cli  → terminal interativo
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

if "--cli" in sys.argv:
    from ui.app import run_app
    run_app()
else:
    from gui.app import run_gui
    run_gui()
