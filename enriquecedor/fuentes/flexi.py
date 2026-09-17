# -*- coding: utf-8 -*-
"""
enriquecedor/fuentes/flexi.py
=============================
Fuente para flexi.com.mx.

El sitio es una SPA de SAP Commerce (Spartacus): el HTML que llega por HTTP
está vacío y el catálogo se pinta con JavaScript. Por eso hace falta un
navegador de verdad — Playwright — y no basta con requests.

Estrategia, en dos tiempos:

  1. ÍNDICE. Se recorren las páginas de categoría públicas y se apuntan todos
     los productos que aparecen. De cada enlace salen gratis el EAN, el estilo
     y el color, porque van en la propia URL.
  2. FICHA. Sólo para los artículos que nos interesan se abre su página y se
     leen título, precio, imágenes y la línea "ID <EAN> - <SAP>", que es el
     puente con el número de artículo del concentrado.

El índice se guarda en disco (indice_flexi.json) para no volver a barrer el
sitio en cada corrida.

Cortesía: una pausa entre peticiones y un tope de páginas. No es un scraper
agresivo; hace lo que haría una persona navegando, más rápido.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..base import FuenteMarca
from ..modelo import Ficha, Solicitud
from . import flexi_parseo as parseo

log = logging.getLogger("enriquecedor.flexi")

BASE = "https://www.flexi.com.mx"

# Categorías públicas por las que se construye el índice.
CATEGORIAS = [
    "/es/Dama/c/Dama",
    "/es/Caballero/c/Caballero",
    "/es/Flexi-Country/c/Flexi_Country",
    "/es/Escolar/c/Escolar",
    "/es/Accesorios/c/Accesorios",
    "/es/Ofertas/c/Ofertas",
    "/es/New-Arrivals/c/New_Arrivals",
]


class FuenteFlexi(FuenteMarca):
    nombre = "flexi"
    sitio = BASE

    def __init__(self, *, ruta_indice: Path | str = "indice_flexi.json",
                 reconstruir_indice: bool = False,
                 paginas_por_categoria: int = 12,
                 pausa_seg: float = 1.0,
                 headless: bool = True,
                 espera_ms: int = 4000):
        self.ruta_indice = Path(ruta_indice)
        self.reconstruir_indice = reconstruir_indice
        self.paginas_por_categoria = paginas_por_categoria
        self.pausa_seg = pausa_seg
        self.headless = headless
        self.espera_ms = espera_ms

        self._pw = None
        self._navegador = None
        self._pagina = None
        self._indice: dict[str, dict] = {}      # llave (ean/estilo) -> {url, estilo, color}

    # ------------------------------------------------------------ ciclo de vida

    def preparar(self) -> None:
        self._abrir_navegador()
        if self.ruta_indice.exists() and not self.reconstruir_indice:
            self._indice = json.loads(self.ruta_indice.read_text(encoding="utf-8"))
            log.info("Índice de Flexi cargado de %s (%d llaves)",
                     self.ruta_indice, len(self._indice))
        else:
            self._construir_indice()

    def cerrar(self) -> None:
        for cerrar in (getattr(self._navegador, "close", None),
                       getattr(self._pw, "stop", None)):
            try:
                if cerrar:
                    cerrar()
            except Exception:
                pass
        self._pw = self._navegador = self._pagina = None

    # ------------------------------------------------------------------ buscar

    def buscar(self, solicitud: Solicitud) -> Ficha | None:
        entrada = None
        for llave in solicitud.llaves():
            entrada = self._indice.get(llave)
            if entrada:
                break

        if entrada is None:
            return None

        html, texto = self._abrir(entrada["url"])
        cruda = parseo.parsear_ficha(html, estilo_esperado=entrada.get("estilo", ""),
                                     texto_visible=texto)

        # Comprobación de identidad: la ficha tiene que corresponder al artículo
        # que pedimos. Si no coincide con ninguna de sus llaves, se descarta:
        # más vale no traer nada que traer el producto equivocado.
        llaves = {l.lower() for l in solicitud.llaves()}
        propias = {v.lower() for v in (cruda.ean, cruda.articulo, cruda.estilo) if v}
        if llaves and propias and not (llaves & propias):
            log.warning("La ficha de %s no coincide con el artículo %s; se descarta.",
                        entrada["url"], solicitud.articulo)
            return None

        return Ficha(
            titulo=cruda.titulo,
            descripcion=cruda.descripcion,
            color=cruda.color or entrada.get("color", ""),
            estilo=cruda.estilo or entrada.get("estilo", ""),
            precio=cruda.precio,
            moneda=cruda.moneda,
            imagenes=cruda.imagenes,
            articulo=cruda.articulo,
            ean=cruda.ean,
            url_fuente=entrada["url"],
            fuente=self.nombre,
        )

    # ----------------------------------------------------------------- interno

    def _abrir_navegador(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Falta Playwright. Instálalo con:\n"
                "    pip install -r requirements-enriquecer.txt\n"
                "    python -m playwright install chromium"
            ) from e

        self._pw = sync_playwright().start()
        self._navegador = self._pw.chromium.launch(headless=self.headless)
        self._pagina = self._navegador.new_page()
        self._pagina.set_default_timeout(45_000)

    def _abrir(self, url: str) -> tuple[str, str]:
        """Abre la URL y devuelve (html, texto_visible)."""
        self._pagina.goto(url, wait_until="domcontentloaded")
        self._pagina.wait_for_timeout(self.espera_ms)
        html = self._pagina.content()
        try:
            texto = self._pagina.inner_text("body")
        except Exception:
            texto = ""
        time.sleep(self.pausa_seg)
        return html, texto

    def _construir_indice(self) -> None:
        log.info("Construyendo el índice de Flexi (esto tarda unos minutos)…")
        indice: dict[str, dict] = {}

        for categoria in CATEGORIAS:
            for pagina in range(self.paginas_por_categoria):
                url = f"{BASE}{categoria}?currentPage={pagina}"
                try:
                    html, _ = self._abrir(url)
                except Exception as e:
                    log.warning("No pude abrir %s: %s", url, e)
                    break

                enlaces = parseo.extraer_enlaces_producto(html, BASE)
                nuevos = 0
                for e in enlaces:
                    registro = {"url": e.url, "estilo": e.estilo, "color": e.color}
                    for llave in filter(None, (e.ean, e.estilo)):
                        if llave not in indice:
                            indice[llave] = registro
                            nuevos += 1
                log.info("  %s pág %d: %d productos (%d llaves nuevas)",
                         categoria, pagina, len(enlaces), nuevos)
                if not enlaces:
                    break

        self._indice = indice
        self.ruta_indice.write_text(json.dumps(indice, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        log.info("Índice guardado en %s con %d llaves.", self.ruta_indice, len(indice))
