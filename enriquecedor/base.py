# -*- coding: utf-8 -*-
"""
enriquecedor/base.py
====================
Interfaz que debe cumplir cada fuente de marca. Agregar una marca nueva
(Onena, la que sea) es escribir una clase que herede de FuenteMarca y
registrarla en fuentes/__init__.py. El motor no se toca.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .modelo import Ficha, Solicitud

log = logging.getLogger("enriquecedor.fuente")


class FuenteMarca(ABC):
    """
    Contrato mínimo de una fuente.

    Ciclo de vida:
        preparar()  -> abre navegador, construye índice, lo que necesite
        buscar(s)   -> una vez por artículo
        cerrar()    -> libera recursos, SIEMPRE se llama

    Reglas que toda fuente debe respetar:
      1. Nunca inventar datos. Si no encontró el producto, devolver None.
      2. Nunca devolver un producto "parecido": o es el mismo identificador
         o no es.
      3. Registrar siempre url_fuente, para que se pueda auditar de dónde
         salió cada dato.
    """

    #: nombre corto de la marca, como aparece en el catálogo
    nombre: str = ""

    #: dominio público de la marca, sólo informativo para el reporte
    sitio: str = ""

    def preparar(self) -> None:
        """Trabajo previo opcional (abrir navegador, construir índice)."""

    def cerrar(self) -> None:
        """Liberar recursos. Se llama aunque haya habido errores."""

    @abstractmethod
    def buscar(self, solicitud: Solicitud) -> Ficha | None:
        """Devuelve la ficha del artículo, o None si no existe en la fuente."""

    def __enter__(self) -> "FuenteMarca":
        self.preparar()
        return self

    def __exit__(self, *_excepcion) -> None:
        self.cerrar()
