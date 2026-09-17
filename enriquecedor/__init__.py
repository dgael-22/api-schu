# -*- coding: utf-8 -*-
"""
enriquecedor
============
Completa productos incompletos con datos publicados por la propia marca.

Reglas que no se negocian:
  · Sólo se llena lo que está vacío. Nunca se pisa un dato del proveedor.
  · Nunca se inventa nada: si la marca no publica el producto, se reporta
    como no encontrado y ya.
  · Todo dato traído de fuera queda marcado con su origen, su URL y su fecha,
    y el producto sale como borrador para que una persona lo revise.
"""

from .modelo import Ficha, Resultado, Solicitud       # noqa: F401
from .motor import Motor, aplicar                      # noqa: F401
from .base import FuenteMarca                          # noqa: F401

__all__ = ["Ficha", "Resultado", "Solicitud", "Motor", "aplicar", "FuenteMarca"]
