# -*- coding: utf-8 -*-
"""
processors/images.py
====================
Manejo de imágenes. En esta primera versión NO se analiza el contenido
visual de las fotos: sólo se separan las URLs, se comprueba que tengan
forma válida y, opcionalmente, se verifica por red que respondan.

La validación por red está apagada por defecto y, cuando se activa, corre en
hilos con timeout: una URL lenta o caída nunca detiene el procesamiento.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from config import rules
from utils.helpers import dividir_por_separadores, texto, unicos_en_orden

log = logging.getLogger("procesador.imagenes")

_URL = re.compile(r"^https?://", re.IGNORECASE)


def extraer_urls(valor) -> list[str]:
    """
    Parte la celda de imágenes por cualquiera de los separadores configurados
    y devuelve las URLs únicas, en el orden original (la primera es la
    principal del producto en Shopify).
    """
    partes = dividir_por_separadores(valor, rules.IMAGEN_SEPARADORES)
    urls = [p.strip().strip('"').strip("'") for p in partes]
    urls = [u for u in urls if u]
    return unicos_en_orden(urls)[:rules.IMAGEN_MAXIMO_POR_PRODUCTO]


def es_url_valida(url: str) -> bool:
    """Comprueba la FORMA de la URL, sin tocar la red."""
    url = texto(url)
    if not url or not _URL.match(url):
        return False
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    if not partes.netloc:
        return False

    ruta = partes.path.lower()
    if rules.IMAGEN_EXTENSIONES_VALIDAS:
        return any(ruta.endswith(ext) for ext in rules.IMAGEN_EXTENSIONES_VALIDAS)
    return True


def clasificar_urls(urls: list[str]) -> tuple[list[str], list[str]]:
    """Devuelve (validas, invalidas) según su forma."""
    validas, invalidas = [], []
    for url in urls:
        (validas if es_url_valida(url) else invalidas).append(url)
    return validas, invalidas


# ---------------------------------------------------------------------------
# Verificación opcional por red
# ---------------------------------------------------------------------------

def _revisar_una(url: str) -> dict:
    resultado = {"url": url, "accesible": False, "codigo": None,
                 "content_type": "", "bytes": None, "error": ""}
    try:
        import urllib.request

        peticion = urllib.request.Request(url, method="HEAD",
                                          headers={"User-Agent": "excel-shopify-processor/1.0"})
        with urllib.request.urlopen(peticion, timeout=rules.IMAGEN_TIMEOUT_SEGUNDOS) as respuesta:
            resultado["codigo"] = respuesta.status
            resultado["content_type"] = respuesta.headers.get("Content-Type", "")
            largo = respuesta.headers.get("Content-Length")
            resultado["bytes"] = int(largo) if largo and largo.isdigit() else None
            resultado["accesible"] = (respuesta.status == 200
                                      and resultado["content_type"].startswith("image/"))
    except Exception as exc:                                   # noqa: BLE001
        resultado["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return resultado


def verificar_urls(urls: list[str]) -> dict[str, dict]:
    """
    Verifica en paralelo que las URLs devuelvan una imagen. Devuelve
    {url: resultado}. Si algo falla se registra, nunca se lanza excepción.
    """
    if not rules.VALIDAR_URLS_IMAGENES or not urls:
        return {}

    unicas = unicos_en_orden(urls)
    if rules.IMAGEN_MAXIMO_A_VALIDAR:
        unicas = unicas[:rules.IMAGEN_MAXIMO_A_VALIDAR]

    log.info("Verificando %d URLs de imagen (timeout %ss, %d hilos)...",
             len(unicas), rules.IMAGEN_TIMEOUT_SEGUNDOS, rules.IMAGEN_HILOS)

    salida: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=rules.IMAGEN_HILOS) as pool:
        futuros = {pool.submit(_revisar_una, u): u for u in unicas}
        for futuro in as_completed(futuros):
            url = futuros[futuro]
            try:
                salida[url] = futuro.result()
            except Exception as exc:                            # noqa: BLE001
                salida[url] = {"url": url, "accesible": False, "codigo": None,
                               "content_type": "", "bytes": None,
                               "error": f"{type(exc).__name__}: {exc}"[:200]}

    fallidas = sum(1 for r in salida.values() if not r["accesible"])
    log.info("Verificación terminada: %d accesibles, %d con problema",
             len(salida) - fallidas, fallidas)
    return salida
