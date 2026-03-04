# -*- coding: utf-8 -*-
"""
Versión centralizada de Raichu - PcComponentes Content Generator.

SINGLE SOURCE OF TRUTH para el número de versión.
Todos los módulos deben importar de aquí:

    from version import __version__

Para actualizar la versión, editar SOLO el archivo VERSION en la raíz.
"""

from pathlib import Path

_VERSION_FILE = Path(__file__).parent / "VERSION"

try:
    __version__ = _VERSION_FILE.read_text().strip()
except FileNotFoundError:
    __version__ = "5.1.0"  # Fallback

__all__ = ["__version__"]
