# -*- coding: utf-8 -*-
"""
processors/validator.py
=======================
Revisa cada producto y cada variante y devuelve una lista de hallazgos.

Principio: un problema en un producto no detiene el proceso. Los hallazgos
de nivel "error" excluyen ese producto del Excel final; los de nivel
"advertencia" lo dejan pasar y quedan anotados en el reporte.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import rules
from processors.products import Producto

log = logging.getLogger("procesador.validador")


MENSAJES = {
    "sku_vacio": "El producto no tiene número de artículo / SKU.",
    "sku_duplicado": "El SKU se repite en otro producto.",
    "titulo_vacio": "El producto no tiene título.",
    "precio_vacio": "Hay tallas sin precio.",
    "precio_invalido": "Hay tallas con un precio que no se pudo convertir a número.",
    "sin_variantes": "El producto no tiene ninguna talla con EAN y precio.",
    "categoria_vacia": "No se pudo determinar la categoría (Type).",
    "talla_vacia": "Hay variantes sin talla.",
    "sin_imagen": "El producto no tiene ninguna imagen válida.",
    "url_invalida": "Ninguna URL de imagen sirvió: sin formato válido o sin respuesta.",
    "url_invalida_parcial": ("Se cargaron las imágenes buenas; algunas URL se "
                             "descartaron por formato inválido o sin respuesta."),
    "sin_color": "El producto no tiene color.",
    "sin_marca": "No se pudo detectar la marca (Vendor queda vacío).",
    "sin_inventario": "El archivo de origen no trae inventario; se exporta en 0.",
    "sin_descripcion": "El producto no tiene descripción.",
    "no_aprobado": ("Se agregó el producto, pero el proveedor no lo marcó como "
                    "aprobado en la columna Aprobación."),
    "handle_duplicado": "El handle chocó con otro producto y se le añadió un sufijo.",
    "variante_duplicada": "Una talla venía repetida; se conservó la primera.",
    "ean_duplicado": "El EAN ya se había usado en otro artículo.",
    "variantes_huerfanas": "Tallas con EAN cuyo artículo no existe en el maestro.",
}


@dataclass
class Hallazgo:
    codigo: str
    nivel: str          # "error" | "advertencia" | "nota"
    handle: str
    articulo: str
    titulo: str
    detalle: str

    @property
    def mensaje(self) -> str:
        return MENSAJES.get(self.codigo, self.codigo)


def _nivel(codigo: str) -> str:
    return rules.NIVEL_VALIDACION.get(codigo, "advertencia")


def validar(productos: list[Producto],
            incidencias_previas: list[dict] | None = None,
            verificacion_imagenes: dict[str, dict] | None = None
            ) -> tuple[list[Producto], list[Producto], list[Hallazgo]]:
    """
    Devuelve (productos_exportables, productos_rechazados, hallazgos).
    """
    hallazgos: list[Hallazgo] = []
    exportables: list[Producto] = []
    rechazados: list[Producto] = []
    verificacion_imagenes = verificacion_imagenes or {}

    # --- SKU duplicado entre productos ---
    conteo_articulos: dict[str, int] = {}
    for producto in productos:
        for articulo in producto.articulos:
            conteo_articulos[articulo] = conteo_articulos.get(articulo, 0) + 1

    for producto in productos:
        problemas: list[str] = list(producto.problemas)
        detalles: dict[str, str] = dict(producto.detalles)

        if not producto.articulo:
            problemas.append("sku_vacio")
        elif conteo_articulos.get(producto.articulo, 0) > 1:
            problemas.append("sku_duplicado")
            detalles["sku_duplicado"] = f"El artículo {producto.articulo} aparece en más de un producto."

        if not producto.titulo:
            problemas.append("titulo_vacio")
        if not producto.body_html:
            problemas.append("sin_descripcion")
        if not producto.vendor:
            problemas.append("sin_marca")
        if not producto.color:
            problemas.append("sin_color")
        if not producto.tipo or producto.tipo == rules.TYPE_POR_DEFECTO:
            problemas.append("categoria_vacia")
        if not producto.variantes:
            problemas.append("sin_variantes")

        # inventario: el concentrado nunca lo trae
        problemas.append("sin_inventario")

        # --- imágenes ---
        # REGLA: basta con que quede UNA imagen buena para que el producto se
        # publique con ella. Las URL malas se descartan y se deja constancia,
        # pero no se castiga al producto entero por una foto rota.
        malas = list(producto.imagenes_invalidas)
        if verificacion_imagenes:
            caidas = [u for u in producto.imagenes
                      if u in verificacion_imagenes
                      and not verificacion_imagenes[u]["accesible"]]
            if caidas:
                # Las que no responden dejan de contar como imagen del producto.
                producto.imagenes = [u for u in producto.imagenes if u not in caidas]
                malas.extend(caidas)

        if not producto.imagenes:
            problemas.append("sin_imagen")
            if malas:
                problemas.append("url_invalida")
                detalles["url_invalida"] = (
                    f"Las {len(malas)} URL(s) del producto fallaron: "
                    + ", ".join(malas[:3]))
        elif malas:
            problemas.append("url_invalida_parcial")
            detalles["url_invalida_parcial"] = (
                f"Se cargaron {len(producto.imagenes)} imagen(es) buena(s); se "
                f"descartaron {len(malas)}: " + ", ".join(malas[:3]))

        # --- variantes ---
        sin_precio = [v for v in producto.variantes if "precio_vacio" in v.problemas]
        precio_malo = [v for v in producto.variantes if "precio_invalido" in v.problemas]
        sin_talla = [v for v in producto.variantes if "talla_vacia" in v.problemas]

        if sin_precio:
            problemas.append("precio_vacio")
            detalles["precio_vacio"] = f"{len(sin_precio)} de {len(producto.variantes)} tallas sin precio."
        if precio_malo:
            problemas.append("precio_invalido")
            detalles["precio_invalido"] = f"{len(precio_malo)} tallas con precio no numérico."
        if sin_talla:
            problemas.append("talla_vacia")
            detalles["talla_vacia"] = f"{len(sin_talla)} variantes sin talla."
        if any("ean_duplicado" in v.problemas for v in producto.variantes):
            problemas.append("ean_duplicado")
        if len(producto.variantes) > rules.MAXIMO_VARIANTES_POR_PRODUCTO:
            problemas.append("sin_variantes")
            detalles["sin_variantes"] = (
                f"{len(producto.variantes)} variantes; el máximo de Shopify es "
                f"{rules.MAXIMO_VARIANTES_POR_PRODUCTO}."
            )

        # --- registrar ---
        vistos = set()
        es_error = False
        for codigo in problemas:
            if codigo in vistos:
                continue
            vistos.add(codigo)
            nivel = _nivel(codigo)
            if nivel == "ninguno":
                continue
            hallazgos.append(Hallazgo(
                codigo=codigo, nivel=nivel, handle=producto.handle,
                articulo=producto.articulo, titulo=producto.titulo,
                detalle=detalles.get(codigo, ""),
            ))
            if nivel == "error":
                es_error = True

        # Un producto sin ninguna variante utilizable no puede ir a Shopify.
        if rules.PRODUCTOS_NO_APROBADOS == "excluir" and "no_aprobado" in vistos:
            es_error = True

        (rechazados if es_error else exportables).append(producto)

    # --- incidencias detectadas antes de la validación ---
    for incidencia in (incidencias_previas or []):
        codigo = incidencia.get("tipo", "otro")
        hallazgos.append(Hallazgo(
            codigo=codigo, nivel=_nivel(codigo), handle="",
            articulo=incidencia.get("articulo", ""), titulo="",
            detalle=incidencia.get("detalle", ""),
        ))

    errores = sum(1 for h in hallazgos if h.nivel == "error")
    log.info("Validación: %d exportables, %d rechazados, %d hallazgos (%d errores)",
             len(exportables), len(rechazados), len(hallazgos), errores)
    return exportables, rechazados, hallazgos
