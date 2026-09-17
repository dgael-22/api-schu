# -*- coding: utf-8 -*-
"""
api/app.py
==========
API HTTP del procesador. Recibe el Excel del proveedor y devuelve el Excel
reorganizado con el formato de Shopify.

Arrancar:
    python servidor.py
    # o bien
    uvicorn api.app:app --reload

Y abrir http://127.0.0.1:8000

Endpoints:
    GET  /                                     página para subir el archivo
    GET  /docs                                 documentación automática
    POST /api/procesar                         sube el Excel y arranca el proceso
    GET  /api/trabajos                         lista de trabajos
    GET  /api/trabajos/{id}                    estado y cifras de un trabajo
    GET  /api/trabajos/{id}/descargar/{qué}    excel | csv | reporte | zip
    DELETE /api/trabajos/{id}                  borra el trabajo y sus archivos
    GET  /api/salud                            comprobación de que está vivo
    GET  /api/configuracion                    reglas activas

La API no toca los archivos de input/ del proyecto: cada subida vive en su
propia carpeta temporal y se borra sola.
"""

from __future__ import annotations

import io
import logging
import shutil
import sys
import time
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from api import trabajos as reg                       # noqa: E402
from api.plantilla_web import PAGINA                  # noqa: E402
from config import rules                              # noqa: E402
from processors.pipeline import procesar_catalogo     # noqa: E402
from api.rutas_enriquecer import montar as montar_enriquecedor  # noqa: E402

log = logging.getLogger("procesador.api")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s %(message)s",
                    datefmt="%H:%M:%S")

# Límites de subida
EXTENSIONES_ORIGEN = {".xlsx", ".xlsm", ".xls"}
EXTENSIONES_PLANTILLA = {".xlsx", ".xlsm", ".csv"}
TAMANO_MAXIMO_MB = 100

REGISTRO = reg.Registro(carpeta_base=RAIZ / "output" / "_api",
                        vida_segundos=3600, maximo=50)

app = FastAPI(
    title="Procesador de catálogos para Shopify",
    description=(
        "Sube el Excel de un proveedor y devuelve el Excel reorganizado con la "
        "estructura que Shopify espera, más un reporte de todo lo que se detectó. "
        "Los datos nunca se inventan: si un campo no viene en el origen, queda vacío "
        "y aparece en el reporte."
    ),
    version="1.0.0",
)

# El enriquecedor vive en su propio módulo y se engancha aquí, para que todo
# corra en el mismo servidor y no haga falta una segunda terminal.
montar_enriquecedor(app, REGISTRO, RAIZ)


# ---------------------------------------------------------------------------
# Proceso en segundo plano
# ---------------------------------------------------------------------------

def _ejecutar(trabajo_id: str, validar_imagenes: bool) -> None:
    trabajo = REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        return

    trabajo.estado = reg.PROCESANDO
    trabajo.mensaje = "Procesando..."
    try:
        plantilla = next(
            (p for p in (trabajo.carpeta / "entrada").glob("plantilla.*")), None)

        resultado = procesar_catalogo(
            ruta_origen=trabajo.ruta_origen,
            carpeta_salida=trabajo.carpeta / "salida",
            ruta_plantilla=plantilla,
            validar_imagenes=validar_imagenes,
        )

        if not resultado.ok:
            trabajo.estado = reg.FALLIDO
            trabajo.mensaje = resultado.error
            trabajo.terminado = time.time()
            log.warning("Trabajo %s falló: %s", trabajo_id, resultado.error)
            return

        trabajo.resumen = resultado.resumen()
        trabajo.archivos = {}
        if resultado.ruta_excel:
            trabajo.archivos["excel"] = resultado.ruta_excel.name
        if resultado.ruta_csv:
            trabajo.archivos["csv"] = resultado.ruta_csv.name
        if resultado.ruta_reporte:
            trabajo.archivos["reporte"] = resultado.ruta_reporte.name

        trabajo.estado = reg.TERMINADO
        trabajo.mensaje = (
            f"{resultado.productos_exportados} productos y "
            f"{resultado.variantes_exportadas} variantes en {resultado.filas_generadas} filas."
        )
        trabajo.terminado = time.time()
        log.info("Trabajo %s terminado: %s", trabajo_id, trabajo.mensaje)

    except Exception as exc:                                    # noqa: BLE001
        trabajo.estado = reg.FALLIDO
        trabajo.mensaje = f"{type(exc).__name__}: {exc}"
        trabajo.terminado = time.time()
        log.exception("Trabajo %s reventó", trabajo_id)


async def _guardar(archivo: UploadFile, destino: Path) -> int:
    """Guarda la subida en disco por trozos, sin cargarla entera en memoria."""
    total = 0
    limite = TAMANO_MAXIMO_MB * 1024 * 1024
    with destino.open("wb") as salida:
        while True:
            trozo = await archivo.read(1024 * 1024)
            if not trozo:
                break
            total += len(trozo)
            if total > limite:
                salida.close()
                destino.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"El archivo pasa de {TAMANO_MAXIMO_MB} MB.")
            salida.write(trozo)
    return total


# ---------------------------------------------------------------------------
# Página web
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def pagina_inicio() -> str:
    return PAGINA


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/salud", tags=["estado"], summary="Comprobar que la API responde")
def salud() -> dict:
    return {
        "estado": "ok",
        "version": app.version,
        "trabajos_activos": len(REGISTRO.listar()),
        "tamano_maximo_mb": TAMANO_MAXIMO_MB,
    }


@app.get("/api/configuracion", tags=["estado"],
         summary="Ver las reglas con las que está corriendo el procesador")
def configuracion() -> dict:
    return {
        "agrupacion": rules.AGRUPACION,
        "estrategia_sku": rules.SKU_ESTRATEGIA,
        "usar_ean_como_barcode": rules.USAR_EAN_COMO_BARCODE,
        "productos_no_aprobados": rules.PRODUCTOS_NO_APROBADOS,
        "option1_name": rules.OPTION1_NAME,
        "hoja_maestro": rules.HOJA_MAESTRO,
        "hojas_variantes": rules.HOJAS_VARIANTES,
        "talla_dividir_entre_10": rules.TALLA_DIVIDIR_ENTRE_10,
        "marcas_conocidas": list(rules.MARCAS_CONOCIDAS),
        "campos_detectables": sorted(rules.COLUMN_ALIASES),
        "columnas_sin_origen": rules.COLUMNAS_SIN_ORIGEN,
    }


@app.get("/api/vocabulario", tags=["estado"],
         summary="Ver el vocabulario cerrado de tags y los filtros de la tienda")
def ver_vocabulario() -> dict:
    from processors import vocabulario
    return vocabulario.exportar()


@app.post("/api/retaguear", tags=["procesar"],
          summary="Reclasificar un export de productos de Shopify con el vocabulario")
async def retaguear(
    archivo: UploadFile = File(..., description="Export de productos de Shopify (.csv)"),
):
    """
    Devuelve un CSV con, por handle: tags, Vendor, Type y los metafields de los
    filtros. **No es para importar en Shopify**.
    """
    from processors.retaguear import retaguear_export

    nombre = Path(archivo.filename or "export.csv").name
    if Path(nombre).suffix.lower() != ".csv":
        raise HTTPException(status_code=415, detail=f"'{nombre}' no es un CSV.")
    trabajo = REGISTRO.crear(nombre)
    entrada = trabajo.carpeta / "entrada" / "export.csv"
    await _guardar(archivo, entrada)
    salida = trabajo.carpeta / "salida" / "organizacion.csv"
    res = retaguear_export(entrada, salida)
    log.info("Retagueo %s: %d productos, tags %d -> %d",
             trabajo.id, res.productos, res.tags_antes, res.tags_despues)
    return FileResponse(salida, filename="organizacion.csv",
                        media_type="text/csv; charset=utf-8",
                        headers={"X-Productos": str(res.productos),
                                 "X-Tags-Antes": str(res.tags_antes),
                                 "X-Tags-Despues": str(res.tags_despues),
                                 "X-A-Revision": str(res.a_revision)})


@app.post("/api/procesar", tags=["procesar"], status_code=202,
          summary="Subir el Excel del proveedor y arrancar el proceso")
async def procesar(
    tareas: BackgroundTasks,
    archivo: UploadFile = File(..., description="Excel del proveedor (.xlsx)"),
    plantilla: UploadFile | None = File(
        None, description="Plantilla de columnas (.xlsx o .csv). Opcional: si no "
                          "se manda se usa la de input/."),
    validar_imagenes: bool = Form(
        False, description="Comprobar por red que cada URL devuelva una imagen. "
                           "Hace el proceso bastante más lento."),
) -> dict:
    """
    Devuelve **202** con el id del trabajo. El proceso corre en segundo plano;
    consulta `GET /api/trabajos/{id}` hasta que el estado sea `terminado` y
    entonces descarga los archivos.
    """
    nombre = Path(archivo.filename or "archivo.xlsx").name
    extension = Path(nombre).suffix.lower()
    if extension not in EXTENSIONES_ORIGEN:
        raise HTTPException(
            status_code=415,
            detail=f"'{nombre}' no es un Excel. Se aceptan: "
                   f"{', '.join(sorted(EXTENSIONES_ORIGEN))}")

    trabajo = REGISTRO.crear(nombre)
    entrada = trabajo.carpeta / "entrada"
    trabajo.ruta_origen = entrada / f"origen{extension}"
    await _guardar(archivo, trabajo.ruta_origen)

    if plantilla is not None and plantilla.filename:
        ext_plantilla = Path(plantilla.filename).suffix.lower()
        if ext_plantilla not in EXTENSIONES_PLANTILLA:
            REGISTRO.borrar(trabajo.id)
            raise HTTPException(
                status_code=415,
                detail=f"La plantilla debe ser {', '.join(sorted(EXTENSIONES_PLANTILLA))}")
        await _guardar(plantilla, entrada / f"plantilla{ext_plantilla}")
    else:
        # Si no mandan plantilla se usa la del proyecto.
        for nombre_plantilla in rules.ARCHIVO_PLANTILLA:
            origen = RAIZ / "input" / nombre_plantilla
            if origen.exists():
                shutil.copy2(origen, entrada / f"plantilla{origen.suffix.lower()}")
                break

    tareas.add_task(_ejecutar, trabajo.id, validar_imagenes)
    log.info("Trabajo %s creado para '%s'", trabajo.id, nombre)
    return trabajo.a_json()


@app.get("/api/trabajos", tags=["procesar"], summary="Listar los trabajos")
def listar(peticion: Request) -> dict:
    base = str(peticion.base_url).rstrip("/")
    return {"trabajos": [t.a_json(base) for t in REGISTRO.listar()]}


@app.get("/api/trabajos/{trabajo_id}", tags=["procesar"],
         summary="Ver el estado y las cifras de un trabajo")
def estado(trabajo_id: str, peticion: Request) -> dict:
    trabajo = REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Ese trabajo no existe o ya caducó.")
    return trabajo.a_json(str(peticion.base_url).rstrip("/"))


@app.get("/api/trabajos/{trabajo_id}/descargar/{cual}", tags=["procesar"],
         summary="Descargar un archivo generado")
def descargar(trabajo_id: str, cual: str):
    """`cual` puede ser: `excel`, `csv`, `reporte`, `enriquecido` o `zip` (todos juntos)."""
    trabajo = REGISTRO.obtener(trabajo_id)
    if trabajo is None:
        raise HTTPException(status_code=404, detail="Ese trabajo no existe o ya caducó.")
    if trabajo.estado != reg.TERMINADO:
        raise HTTPException(
            status_code=409,
            detail=f"El trabajo está en estado '{trabajo.estado}': {trabajo.mensaje}")

    salida = trabajo.carpeta / "salida"

    if cual == "zip":
        memoria = io.BytesIO()
        with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as zf:
            for nombre in trabajo.archivos.values():
                ruta = salida / nombre
                if ruta.exists():
                    zf.write(ruta, nombre)
        memoria.seek(0)
        return StreamingResponse(
            memoria, media_type="application/zip",
            headers={"Content-Disposition":
                     f'attachment; filename="resultado_{trabajo.id}.zip"'})

    nombre = trabajo.archivos.get(cual)
    if not nombre:
        raise HTTPException(
            status_code=404,
            detail=f"'{cual}' no existe. Disponibles: "
                   f"{', '.join(list(trabajo.archivos) + ['zip'])}")

    ruta = salida / nombre
    if not ruta.exists():
        raise HTTPException(status_code=410, detail="El archivo ya se borró.")

    tipos = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv; charset=utf-8",
    }
    return FileResponse(ruta, filename=nombre,
                        media_type=tipos.get(ruta.suffix.lower(),
                                             "application/octet-stream"))


@app.delete("/api/trabajos/{trabajo_id}", tags=["procesar"],
            summary="Borrar un trabajo y sus archivos")
def borrar(trabajo_id: str) -> dict:
    if not REGISTRO.borrar(trabajo_id):
        raise HTTPException(status_code=404, detail="Ese trabajo no existe.")
    return {"borrado": trabajo_id}


@app.on_event("startup")
def al_arrancar() -> None:
    borrados = REGISTRO.limpiar()
    log.info("API lista. Trabajos caducados eliminados: %d", borrados)
    log.info("Abre http://127.0.0.1:8000 para subir un archivo.")
