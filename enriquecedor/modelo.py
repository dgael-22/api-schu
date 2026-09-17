# -*- coding: utf-8 -*-
"""
enriquecedor/modelo.py
======================
Estructuras que viajan entre el motor y las fuentes. No dependen de ninguna
marca ni de ningún sitio: son el contrato común.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Solicitud:
    """Lo que sabemos de un artículo incompleto y queremos completar."""
    articulo: str                       # número interno (SAP) — la llave del catálogo
    marca: str = ""                     # "flexi", "quirelli", "onena"...
    eans: list[str] = field(default_factory=list)
    estilo: str = ""
    color: str = ""
    titulo: str = ""

    def llaves(self) -> list[str]:
        """Todos los identificadores con los que se puede buscar, sin repetir."""
        vistos, salida = set(), []
        for valor in [self.articulo, *self.eans, self.estilo]:
            v = (valor or "").strip()
            if v and v not in vistos:
                vistos.add(v)
                salida.append(v)
        return salida


@dataclass
class Ficha:
    """Lo que una fuente encontró. Todo campo puede venir vacío."""
    titulo: str = ""
    descripcion: str = ""
    color: str = ""
    estilo: str = ""
    precio: str = ""
    moneda: str = ""
    imagenes: list[str] = field(default_factory=list)
    articulo: str = ""                  # SAP, si la fuente lo publica
    ean: str = ""
    url_fuente: str = ""
    fuente: str = ""                    # nombre de la fuente que la trajo
    consultado_en: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def tiene_algo(self) -> bool:
        return bool(self.titulo or self.descripcion or self.imagenes)


@dataclass
class Resultado:
    """Qué pasó con cada solicitud."""
    solicitud: Solicitud
    ficha: Ficha | None = None
    campos_llenados: list[str] = field(default_factory=list)
    motivo: str = ""                    # por qué no se encontró, si aplica

    @property
    def encontrado(self) -> bool:
        return self.ficha is not None and self.ficha.tiene_algo()
