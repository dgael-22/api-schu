# -*- coding: utf-8 -*-
"""
enriquecedor/fuentes/flexi_parseo.py
====================================
Parseo del HTML de flexi.com.mx. Está separado del navegador a propósito:
así se puede probar con HTML guardado, sin red y sin Playwright.

Lo que se observó en el sitio (7-sep-2026), y sobre lo que está escrito esto:

  · Enlace de producto:
        /es/producto/7500421982280-sneaker-suela-con-gel-flexi-para-mujer-estilo-138801-negro
    Empieza con el EAN, y el slug termina en "estilo-<estilo>-<color>".

  · Ficha de producto: trae JSON-LD schema.org/Product con
        sku (el EAN), name, image y offers{price, priceCurrency, availability}

  · La ficha muestra en texto la línea de referencia cruzada:
        ID 7500421982280 - 1390037904
    es decir  EAN - número SAP. Ése es el puente con el concentrado.

  · Las imágenes viven en apiecom.flexi.com.mx/medias/<estilo>-<color>-<vista>.jpg
    con un token ?context=... firmado. El token NO se puede inventar: la URL
    hay que leerla de la página tal cual.

Si el sitio cambia, esto es lo único que hay que ajustar.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# --- Expresiones sobre lo observado ----------------------------------------

RE_ENLACE = re.compile(r'/es/producto/(\d{8,14})-([a-z0-9\-]+)', re.IGNORECASE)
RE_ESTILO_COLOR = re.compile(r'estilo-([a-z0-9]+)-(.+)$', re.IGNORECASE)
RE_ID_CRUZADO = re.compile(r'ID\s*(\d{8,14})\s*-\s*(\d{6,14})')
RE_JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE)
RE_IMAGEN = re.compile(
    r'https://[a-z0-9.\-]*flexi\.com\.mx/medias/([A-Za-z0-9]+)-([a-z\-]+?)-([a-z\-]+)\.jpg[^"\'\s\\]*',
    re.IGNORECASE)


@dataclass
class EnlaceProducto:
    ean: str
    slug: str
    url: str
    estilo: str = ""
    color: str = ""

    @property
    def titulo_probable(self) -> str:
        """Título reconstruido del slug. Sólo orientativo: el bueno es el de la ficha."""
        return " ".join(p.capitalize() for p in self.slug.split("-"))


@dataclass
class FichaFlexi:
    ean: str = ""
    articulo: str = ""          # número SAP
    titulo: str = ""
    estilo: str = ""
    color: str = ""
    precio: str = ""
    moneda: str = ""
    disponibilidad: str = ""
    imagenes: list[str] = field(default_factory=list)
    descripcion: str = ""


def _normalizar_color(texto: str) -> str:
    """'negro' -> 'Negro'; 'rojo-gris' -> 'Rojo - Gris' (como lo escribe el concentrado)."""
    partes = [p for p in texto.split("-") if p]
    return " - ".join(p.capitalize() for p in partes)


def extraer_enlaces_producto(html: str, base: str = "https://www.flexi.com.mx") -> list[EnlaceProducto]:
    """
    Saca todos los productos de una página de listado, sin depender de clases
    CSS: se apoya sólo en la forma de la URL, que es lo más estable del sitio.
    """
    vistos: set[str] = set()
    salida: list[EnlaceProducto] = []

    for ean, slug in RE_ENLACE.findall(html or ""):
        slug = slug.rstrip("-").lower()
        if ean in vistos:
            continue
        vistos.add(ean)

        estilo = color = ""
        m = RE_ESTILO_COLOR.search(slug)
        if m:
            estilo = m.group(1)
            color = _normalizar_color(m.group(2))

        salida.append(EnlaceProducto(
            ean=ean, slug=slug, url=f"{base}/es/producto/{ean}-{slug}",
            estilo=estilo, color=color))
    return salida


def _leer_jsonld(html: str) -> dict:
    """Devuelve el primer bloque JSON-LD que sea un Product."""
    for bloque in RE_JSONLD.findall(html or ""):
        try:
            datos = json.loads(bloque.strip())
        except json.JSONDecodeError:
            continue
        candidatos = datos if isinstance(datos, list) else [datos]
        for c in candidatos:
            if isinstance(c, dict) and c.get("@type") == "Product":
                return c
    return {}


def extraer_imagenes(html: str, estilo: str = "", color: str = "") -> list[str]:
    """
    URLs de imagen del producto, en el orden en que aparecen y sin repetir.

    Si se conoce el estilo y el color, se filtran las de OTROS colores: la
    ficha también muestra miniaturas de las variantes de color, y ésas no son
    de este producto.
    """
    estilo_n = (estilo or "").lower()
    color_n = (color or "").replace(" - ", "-").replace(" ", "-").lower()

    vistas: set[str] = set()
    salida: list[str] = []
    for m in RE_IMAGEN.finditer(html or ""):
        url = m.group(0)
        est, col = m.group(1).lower(), m.group(2).lower()
        if estilo_n and est != estilo_n:
            continue
        if color_n and col != color_n:
            continue
        clave = f"{est}-{col}-{m.group(3).lower()}"
        if clave in vistas:
            continue
        vistas.add(clave)
        salida.append(url)
    return salida


def parsear_ficha(html: str, *, estilo_esperado: str = "", texto_visible: str = "") -> FichaFlexi:
    """
    Arma la ficha a partir del HTML. `texto_visible` es opcional: si se pasa el
    innerText de la página, se usa para la línea "ID <ean> - <sap>", que no
    siempre viene en el HTML servido.
    """
    ficha = FichaFlexi()
    producto = _leer_jsonld(html)

    ficha.ean = str(producto.get("sku") or "")
    ficha.titulo = (producto.get("name") or "").strip()

    oferta = producto.get("offers") or {}
    if isinstance(oferta, list):
        oferta = oferta[0] if oferta else {}
    if isinstance(oferta, dict):
        precio = oferta.get("price")
        ficha.precio = "" if precio is None else str(precio)
        ficha.moneda = oferta.get("priceCurrency") or ""
        ficha.disponibilidad = oferta.get("availability") or ""

    # Estilo y color se leen del título, que es donde el sitio los escribe:
    # "Sneaker Suela Con Gel Flexi para Mujer Estilo 138801 Negro"
    m = re.search(r"estilo\s+([A-Za-z0-9\-]+)\s+(.+)$", ficha.titulo, re.IGNORECASE)
    if m:
        ficha.estilo = m.group(1)
        ficha.color = m.group(2).strip()
    elif estilo_esperado:
        ficha.estilo = estilo_esperado

    # Referencia cruzada EAN <-> SAP
    cruz = RE_ID_CRUZADO.search(texto_visible or "") or RE_ID_CRUZADO.search(html or "")
    if cruz:
        if not ficha.ean:
            ficha.ean = cruz.group(1)
        ficha.articulo = cruz.group(2)

    ficha.imagenes = extraer_imagenes(html, ficha.estilo, ficha.color)
    return ficha
