# -*- coding: utf-8 -*-
"""
enriquecedor/fuentes/__init__.py
================================
Registro de fuentes. AQUÍ se agrega una marca nueva.

Para dar de alta Onena (o la que sea):

  1. Copia flexi.py a onena.py y ajusta:
       - BASE y CATEGORIAS con las URLs reales de su sitio
       - el parseo en su propio módulo, con las formas que use ESE sitio
  2. Agrégala al diccionario FUENTES de abajo.
  3. Listo: el motor, el CLI y el reporte no se tocan.

Si el sitio de la marca NO es una SPA, ni siquiera hace falta Playwright:
basta con una fuente que baje el HTML y lo parsee.
"""

from __future__ import annotations

from ..base import FuenteMarca
from .flexi import FuenteFlexi

#: marca (en minúsculas, como viene en el catálogo) -> clase de la fuente
FUENTES: dict[str, type[FuenteMarca]] = {
    "flexi": FuenteFlexi,
    # "quirelli": FuenteQuirelli,     # pendiente: falta ver su sitio
    # "onena":    FuenteOnena,        # pendiente: falta el Excel y su sitio
}


def crear(marca: str, **opciones) -> FuenteMarca | None:
    """Instancia la fuente de una marca, o None si no hay ninguna registrada."""
    clase = FUENTES.get((marca or "").strip().lower())
    return clase(**opciones) if clase else None


def marcas_soportadas() -> list[str]:
    return sorted(FUENTES)
