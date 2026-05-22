#!/usr/bin/env python3
"""Conferidor de Loterias Caixa – entry point."""
import sys
import os

# Ensure project root is on the path when run directly
sys.path.insert(0, os.path.dirname(__file__))

from ui.app import run_app

if __name__ == "__main__":
    run_app()
