# -*- coding: utf-8 -*-
"""
enriquecedor/motor.py
=====================
Orquesta el enriquecimiento. Es el único lugar donde se decide QUÉ se
rellena, y su regla es una sola:

    Sólo se escribe donde no había nada.

Nunca pisa un dato que el proveedor ya mandó, ni siquiera si el de la marca
"se ve mejor". Si los dos existen y difieren, se anota como discrepancia para
que una persona la revise.

Todo lo que llena queda marcado con su origen y su fecha, y los productos
enriquecidos salen para revisión humana, no directo a publicación.
"""

from __future__ import annotations

import logging
from dataclasses import fields as campos_de

from .base import FuenteMarca
from .modelo import Ficha, Resultado, Solicitud

log = logging.getLogger("enriquecedor.motor")

#: Campos de Ficha que se pueden volcar a un producto.
CAMPOS_LLENABLES = ("titulo", "descripcion", "color", "estilo", "precio", "imagenes")


class Motor:
    def __init__(self, fuentes: dict[str, FuenteMarca], *, limite: int | None = None):
        """
        fuentes: {marca_en_minúsculas: FuenteMarca}
        limite:  tope de artículos a consultar (útil para probar sin barrer todo)
        """
        self.fuentes = {k.lower(): v for k, v in fuentes.items()}
        self.limite = limite
        self.discrepancias: list[dict] = []

    # ------------------------------------------------------------------ API

    def enriquecer(self, solicitudes: list[Solicitud]) -> list[Resultado]:
        # Con `limite` puesto (que es como se prueba), primero van las marcas que
        # SÍ tienen fuente: si no, un tope de 1 puede caer en una marca sin
        # adaptador y la prueba no dice nada útil.
        if self.limite:
            con_fuente = [s for s in solicitudes if (s.marca or "").lower() in self.fuentes]
            sin_fuente = [s for s in solicitudes if (s.marca or "").lower() not in self.fuentes]
            pendientes = (con_fuente + sin_fuente)[: self.limite]
        else:
            pendientes = solicitudes
        resultados: list[Resultado] = []

        por_marca: dict[str, list[Solicitud]] = {}
        for s in pendientes:
            por_marca.setdefault((s.marca or "").lower(), []).append(s)

        for marca, lote in por_marca.items():
            fuente = self.fuentes.get(marca)
            if fuente is None:
                log.warning("No hay fuente configurada para la marca '%s'; %d artículos "
                            "se quedan sin enriquecer.", marca or "(vacía)", len(lote))
                resultados += [Resultado(solicitud=s,
                                         motivo=f"sin fuente para la marca '{marca}'")
                               for s in lote]
                continue

            log.info("Marca '%s': %d artículos por consultar en %s",
                     marca, len(lote), fuente.sitio or fuente.nombre)
            try:
                fuente.preparar()
                for solicitud in lote:
                    resultados.append(self._una(fuente, solicitud))
            finally:
                fuente.cerrar()

        encontrados = sum(1 for r in resultados if r.encontrado)
        log.info("Enriquecimiento terminado: %d de %d artículos encontrados",
                 encontrados, len(resultados))
        return resultados

    # -------------------------------------------------------------- interno

    def _una(self, fuente: FuenteMarca, solicitud: Solicitud) -> Resultado:
        try:
            ficha = fuente.buscar(solicitud)
        except Exception as e:                      # una falla no tumba el lote
            log.warning("Error consultando %s en %s: %s",
                        solicitud.articulo, fuente.nombre, e)
            return Resultado(solicitud=solicitud, motivo=f"error de la fuente: {e}")

        if ficha is None or not ficha.tiene_algo():
            return Resultado(solicitud=solicitud,
                             motivo="la marca no publica ese artículo en su sitio")

        ficha.fuente = ficha.fuente or fuente.nombre
        self._anotar_discrepancias(solicitud, ficha)
        return Resultado(solicitud=solicitud, ficha=ficha,
                         campos_llenados=self._campos_utiles(solicitud, ficha))

    @staticmethod
    def _campos_utiles(solicitud: Solicitud, ficha: Ficha) -> list[str]:
        """Qué campos aporta la ficha que el artículo NO tenía."""
        utiles = []
        for campo in CAMPOS_LLENABLES:
            valor_nuevo = getattr(ficha, campo, None)
            if not valor_nuevo:
                continue
            valor_viejo = getattr(solicitud, campo, "") if hasattr(solicitud, campo) else ""
            if not valor_viejo:
                utiles.append(campo)
        return utiles

    def _anotar_discrepancias(self, solicitud: Solicitud, ficha: Ficha) -> None:
        """Si el proveedor y la marca dicen cosas distintas, se registra."""
        for campo in ("estilo", "color", "titulo"):
            viejo = (getattr(solicitud, campo, "") or "").strip().lower()
            nuevo = (getattr(ficha, campo, "") or "").strip().lower()
            if viejo and nuevo and viejo != nuevo:
                self.discrepancias.append({
                    "articulo": solicitud.articulo,
                    "campo": campo,
                    "en_el_excel": getattr(solicitud, campo),
                    "en_la_marca": getattr(ficha, campo),
                    "url": ficha.url_fuente,
                })


def aplicar(destino: dict, ficha: Ficha, *, campos=CAMPOS_LLENABLES) -> list[str]:
    """
    Vuelca la ficha sobre un diccionario de producto SIN pisar nada.
    Devuelve los nombres de los campos que efectivamente se llenaron.

    Se usa así en vez de escribir directo sobre las entidades del procesador,
    para que el enriquecedor sirva igual con cualquier estructura de destino.
    """
    llenados = []
    for campo in campos:
        nuevo = getattr(ficha, campo, None)
        if not nuevo:
            continue
        actual = destino.get(campo)
        if actual:                       # ya había dato: no se toca
            continue
        destino[campo] = nuevo
        llenados.append(campo)

    if llenados:
        destino["_origen_datos"] = ficha.fuente
        destino["_url_origen"] = ficha.url_fuente
        destino["_enriquecido_en"] = ficha.consultado_en
        destino["_campos_enriquecidos"] = ", ".join(llenados)
        # Un producto que se completó con datos de fuera NO se publica solo.
        destino["estatus"] = "draft"
    return llenados


def _nombres_de_ficha() -> list[str]:
    return [c.name for c in campos_de(Ficha)]
