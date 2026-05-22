#!/usr/bin/env python3
"""
Conferidor de Loterias Caixa
  python main.py        → interface web (padrão)
  python main.py --cli  → terminal interativo
  python main.py --gui  → interface gráfica (requer display)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

if "--cli" in sys.argv:
    from ui.app import run_app
    run_app()
elif "--gui" in sys.argv:
    from gui.app import run_gui
    run_gui()
else:
    from app_web import run_web
    run_web(host="127.0.0.1", port=5000, debug=False, open_browser=True)
