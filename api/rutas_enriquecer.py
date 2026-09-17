# -*- coding: utf-8 -*-
"""
api/rutas_enriquecer.py
=======================
Endpoints del enriquecedor, para que TODO viva en el mismo servidor y no haga
falta una segunda terminal.

Se engancha en api/app.py con dos líneas:

    from api.rutas_enriquecer import montar          # arriba, con los imports
    montar(app, REGISTRO, RAIZ)                      # después de crear `app`

Es un módulo aparte a propósito: app.py no se reescribe, sólo se le agrega el
router. Si algún día se quiere quitar el enriquecedor, se borran esas dos
líneas y el procesador queda igual que antes.

Flujo:
    POST /api/trabajos/{id}/enriquecer            artículos incompletos
    POST /api/trabajos/{id}/enriquecer-imagenes   fotos que faltan
    GET  /api/trabajos/{id}                       el estado de siempre
    GET  /api/trabajos/{id}/descargar/enriquecido
    GET  /api/trabajos/{id}/descargar/imagenes        (reporte .xlsx)
    GET  /api/trabajos/{id}/descargar/imagenes_csv    (listo para importar)

Enriquecer abre un navegador y tarda minutos, así que NUNCA se hace dentro del
request: se lanza como tarea de fondo, igual que el procesamiento.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from api import trabajos as reg
from enriquecedor.fuentes import marcas_soportadas
from enriquecedor.tarea import enriquecer_catalogo, enriquecer_imagenes

log = logging.getLogger("procesador.api.enriquecer")

router = APIRouter()

_REGISTRO = None
_RAIZ: Path | None = None


def montar(app, registro, raiz: Path) -> None:
    """Engancha estas rutas en la app del procesador."""
    global _REGISTRO, _RAIZ
    _REGISTRO, _RAIZ = registro, Path(raiz)
    app.include_router(router)
    log.info("Enriquecedor montado en la API (marcas: %s)", marcas_soportadas())


def _ejecutar(trabajo_id: str, marca: str, limite: int | None,
              reconstruir: bool) -> None:
    trabajo = _REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        return

    salida = trabajo.carpeta / "salida"
    reporte = salida / trabajo.archivos.get("reporte", "reporte_proceso.xlsx")

    estado_previo, mensaje_previo = trabajo.estado, trabajo.mensaje
    trabajo.estado = reg.PROCESANDO
    trabajo.mensaje = "Enriqueciendo con el sitio de la marca (tarda minutos)..."

    try:
        resultado = enriquecer_catalogo(
            ruta_reporte=reporte,
            ruta_salida=salida / "enriquecido.xlsx",
            ruta_origen=trabajo.ruta_origen,
            marca_por_defecto=marca,
            limite=limite,
            # El índice se comparte entre trabajos: barrer el sitio una vez basta.
            carpeta_indices=_RAIZ / "output",
            reconstruir_indice=reconstruir,
            headless=True,
        )
    except Exception as exc:                                    # noqa: BLE001
        trabajo.estado = estado_previo
        trabajo.mensaje = f"{mensaje_previo} · Enriquecer falló: {type(exc).__name__}: {exc}"
        log.warning("Enriquecimiento de %s falló: %s", trabajo_id, exc)
        return

    trabajo.estado = estado_previo          # el procesamiento sigue estando bien
    trabajo.terminado = time.time()

    if not resultado.ok:
        trabajo.mensaje = f"{mensaje_previo} · Enriquecer falló: {resultado.error}"
        log.warning("Enriquecimiento de %s falló: %s", trabajo_id, resultado.error)
        return

    if resultado.ruta_salida:
        trabajo.archivos["enriquecido"] = resultado.ruta_salida.name
    trabajo.resumen["enriquecimiento"] = resultado.resumen()
    trabajo.mensaje = (
        f"{mensaje_previo} · Enriquecido: {resultado.encontrados} encontrados de "
        f"{resultado.solicitados}, {resultado.discrepancias} discrepancias."
    )
    log.info("Enriquecimiento de %s terminado: %s", trabajo_id, trabajo.mensaje)


@router.post("/api/trabajos/{trabajo_id}/enriquecer", tags=["enriquecer"],
             status_code=202,
             summary="Completar los artículos incompletos con el sitio de la marca")
def enriquecer(trabajo_id: str, tareas: BackgroundTasks,
               marca: str = Query("flexi", description="Marca por defecto"),
               limite: int | None = Query(None, ge=1,
                                          description="Tope de artículos, para probar"),
               reconstruir_indice: bool = Query(False)) -> dict:
    """
    Devuelve **202**. Corre en segundo plano: consulta `GET /api/trabajos/{id}`
    y, cuando aparezca la descarga `enriquecido`, bájala con
    `GET /api/trabajos/{id}/descargar/enriquecido`.

    Requiere el trabajo ya **terminado**: el enriquecedor parte del reporte que
    generó el procesamiento.
    """
    if _REGISTRO is None:
        raise HTTPException(status_code=500, detail="El enriquecedor no está montado.")

    trabajo = _REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Ese trabajo no existe o ya caducó.")
    if trabajo.estado != reg.TERMINADO:
        raise HTTPException(
            status_code=409,
            detail=f"El trabajo está en estado '{trabajo.estado}'. "
                   f"Enriquecer necesita el reporte del procesamiento ya terminado.")
    if "reporte" not in trabajo.archivos:
        raise HTTPException(status_code=409,
                            detail="Ese trabajo no generó reporte; no hay de dónde partir.")

    tareas.add_task(_ejecutar, trabajo_id, marca, limite, reconstruir_indice)
    return {"id": trabajo_id, "estado": "enriqueciendo",
            "mensaje": "Arrancó en segundo plano. Consulta el estado del trabajo.",
            "aviso": "Abre un navegador y tarda minutos. Usa 'limite' para probar."}


def _ejecutar_imagenes(trabajo_id: str, marca: str, minimo: int,
                       limite: int | None, reconstruir: bool) -> None:
    trabajo = _REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        return

    salida = trabajo.carpeta / "salida"
    export = salida / trabajo.archivos.get("csv", "")
    if not export.exists():
        export = salida / trabajo.archivos.get("excel", "")

    estado_previo, mensaje_previo = trabajo.estado, trabajo.mensaje
    trabajo.estado = reg.PROCESANDO
    trabajo.mensaje = "Buscando las imágenes que faltan en el sitio de la marca..."

    try:
        resultado = enriquecer_imagenes(
            ruta_export=export,
            ruta_salida=salida / "imagenes_encontradas.xlsx",
            minimo=minimo,
            marca_por_defecto=marca,
            limite=limite,
            carpeta_indices=_RAIZ / "output",
            reconstruir_indice=reconstruir,
            headless=True,
        )
    except Exception as exc:                                    # noqa: BLE001
        trabajo.estado = estado_previo
        trabajo.mensaje = f"{mensaje_previo} · Imágenes: falló ({type(exc).__name__}: {exc})"
        log.warning("Imágenes de %s falló: %s", trabajo_id, exc)
        return

    trabajo.estado = estado_previo
    trabajo.terminado = time.time()

    if not resultado.ok:
        trabajo.mensaje = f"{mensaje_previo} · Imágenes: falló ({resultado.error})"
        log.warning("Imágenes de %s falló: %s", trabajo_id, resultado.error)
        return

    if resultado.solicitados == 0:
        trabajo.mensaje = (f"{mensaje_previo} · Imágenes: todos los productos ya "
                           f"tienen al menos {minimo}.")
        return

    if resultado.ruta_salida:
        trabajo.archivos["imagenes"] = resultado.ruta_salida.name
        csv = resultado.ruta_salida.with_name(resultado.ruta_salida.stem + "_shopify.csv")
        if csv.exists():
            trabajo.archivos["imagenes_csv"] = csv.name
    trabajo.resumen["imagenes"] = resultado.resumen()
    trabajo.mensaje = (
        f"{mensaje_previo} · Imágenes: {resultado.encontrados} de "
        f"{resultado.solicitados} productos resueltos.")
    log.info("Imágenes de %s terminado: %s", trabajo_id, trabajo.mensaje)


@router.post("/api/trabajos/{trabajo_id}/enriquecer-imagenes", tags=["enriquecer"],
             status_code=202,
             summary="Traer del sitio de la marca las imágenes que faltan")
def enriquecer_fotos(trabajo_id: str, tareas: BackgroundTasks,
                     marca: str = Query("flexi", description="Marca por defecto"),
                     minimo: int = Query(1, ge=1,
                                         description="Cuántas fotos debe tener un "
                                                     "producto para dejarlo en paz"),
                     limite: int | None = Query(None, ge=1,
                                                description="Tope de productos, para probar"),
                     reconstruir_indice: bool = Query(False)) -> dict:
    """
    Busca en el sitio de la marca las fotos de los productos que salieron con
    menos de `minimo` imágenes, y deja dos descargas:

    * `imagenes` — el reporte: qué encontró, qué no y por qué
    * `imagenes_csv` — `Handle`, `Image Src`, `Image Position`, listo para
      importar en Shopify y agregar sólo las fotos

    Nada se publica solo: el CSV se revisa antes de importarlo.
    """
    if _REGISTRO is None:
        raise HTTPException(status_code=500, detail="El enriquecedor no está montado.")

    trabajo = _REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Ese trabajo no existe o ya caducó.")
    if trabajo.estado != reg.TERMINADO:
        raise HTTPException(
            status_code=409,
            detail=f"El trabajo está en estado '{trabajo.estado}'. Las imágenes se "
                   f"buscan sobre el catálogo ya procesado.")
    if not ("csv" in trabajo.archivos or "excel" in trabajo.archivos):
        raise HTTPException(status_code=409,
                            detail="Ese trabajo no generó catálogo; no hay de dónde partir.")

    tareas.add_task(_ejecutar_imagenes, trabajo_id, marca, minimo, limite,
                    reconstruir_indice)
    return {"id": trabajo_id, "estado": "buscando_imagenes",
            "mensaje": "Arrancó en segundo plano. Consulta el estado del trabajo.",
            "aviso": "Abre un navegador y tarda minutos. Usa 'limite' para probar."}


@router.get("/api/enriquecer/marcas", tags=["enriquecer"],
            summary="Marcas con fuente registrada")
def marcas() -> dict:
    return {"marcas": marcas_soportadas()}
