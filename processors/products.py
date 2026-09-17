# -*- coding: utf-8 -*-
"""
processors/products.py
======================
Corazón del proyecto: convierte el maestro de producto-color más las hojas de
tallas/EAN/precio en objetos Producto con sus Variantes, listos para volcarse
al formato de Shopify.

La agrupación se decide en config/rules.AGRUPACION:
  - "articulo"      : un producto de Shopify por estilo+color (Option1=Talla)
  - "producto_base" : un producto por estilo (Option1=Talla, Option2=Color)

Nunca se agrupan productos por parecido de nombre: sólo por el identificador
real que trae el archivo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from config import rules
from processors import cleaner, images, normalizer
from utils.helpers import texto

log = logging.getLogger("procesador.productos")


# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------

@dataclass
class Variante:
    articulo: str = ""          # número SAP del producto-color
    talla: str = ""
    color: str = ""
    sku: str = ""
    barcode: str = ""
    precio: str = ""
    problemas: list[str] = field(default_factory=list)
    fila_origen: str = ""


@dataclass
class Producto:
    handle: str = ""
    articulo: str = ""
    estilo: str = ""
    titulo: str = ""
    body_html: str = ""
    vendor: str = ""
    tipo: str = ""
    tags: str = ""
    color: str = ""
    familia: str = ""
    linea: str = ""
    aprobacion: str = ""
    publicado: str = "true"
    estatus: str = "active"
    variantes: list[Variante] = field(default_factory=list)
    imagenes: list[str] = field(default_factory=list)
    imagenes_invalidas: list[str] = field(default_factory=list)
    articulos: list[str] = field(default_factory=list)   # todos los SAP del grupo
    problemas: list[str] = field(default_factory=list)
    detalles: dict = field(default_factory=dict)        # {codigo: explicación}

    @property
    def option1_name(self) -> str:
        return rules.OPTION1_NAME

    @property
    def option2_name(self) -> str:
        if rules.AGRUPACION == "producto_base" and any(v.color for v in self.variantes):
            return rules.OPTION2_NAME
        return ""


# ---------------------------------------------------------------------------
# Variantes
# ---------------------------------------------------------------------------

def construir_variantes(df_variantes: pd.DataFrame, mapa: dict[str, str]) -> tuple[dict[str, list[Variante]], list[dict]]:
    """
    Agrupa las filas de las hojas de EAN por número de artículo.
    Devuelve ({articulo: [Variante...]}, incidencias).
    """
    col_art = mapa["var_articulo"]
    col_talla = mapa["var_talla"]
    col_precio = mapa["var_precio"]
    col_ean = mapa.get("var_ean")

    por_articulo: dict[str, list[Variante]] = {}
    incidencias: list[dict] = []
    vistas: set[tuple[str, str]] = set()
    eans_vistos: dict[str, str] = {}

    for posicion, fila in df_variantes.iterrows():
        articulo = cleaner.limpiar_identificador(fila.get(col_art))
        if not articulo:
            incidencias.append({
                "tipo": "variante_sin_articulo",
                "hoja": texto(fila.get("_hoja_origen")),
                "fila_excel": int(posicion) + 2,
                "detalle": "Fila de talla sin número de artículo; se descarta.",
            })
            continue

        talla = normalizer.normalizar_talla(fila.get(col_talla))
        precio, error_precio = cleaner.limpiar_precio(fila.get(col_precio))
        ean = cleaner.limpiar_identificador(fila.get(col_ean)) if col_ean else ""

        variante = Variante(
            articulo=articulo,
            talla=talla,
            barcode=ean if rules.USAR_EAN_COMO_BARCODE else "",
            precio=precio,
            fila_origen=f"{texto(fila.get('_hoja_origen'))}!{int(posicion) + 2}",
        )

        if error_precio:
            variante.problemas.append(error_precio)
        if not talla:
            variante.problemas.append("talla_vacia")

        clave = (articulo, talla)
        if clave in vistas:
            variante.problemas.append("variante_duplicada")
            incidencias.append({
                "tipo": "variante_duplicada",
                "articulo": articulo,
                "detalle": f"La talla '{talla}' aparece más de una vez para el artículo {articulo}.",
                "fila_excel": variante.fila_origen,
            })
            continue    # se conserva la primera aparición
        vistas.add(clave)

        if ean:
            if ean in eans_vistos and eans_vistos[ean] != articulo:
                variante.problemas.append("ean_duplicado")
                incidencias.append({
                    "tipo": "ean_duplicado",
                    "articulo": articulo,
                    "detalle": f"El EAN {ean} ya se usó en el artículo {eans_vistos[ean]}.",
                    "fila_excel": variante.fila_origen,
                })
            else:
                eans_vistos[ean] = articulo

        por_articulo.setdefault(articulo, []).append(variante)

    # Ordenar tallas dentro de cada artículo
    for articulo, lista in por_articulo.items():
        lista.sort(key=lambda v: normalizer.clave_orden_talla(v.talla))

    log.info("Variantes agrupadas: %d artículos, %d variantes en total",
             len(por_articulo), sum(len(v) for v in por_articulo.values()))
    return por_articulo, incidencias


# ---------------------------------------------------------------------------
# Productos
# ---------------------------------------------------------------------------

def _fila_a_producto(fila: pd.Series, mapa: dict[str, str]) -> Producto:
    def campo(nombre: str) -> str:
        columna = mapa.get(nombre)
        return texto(fila.get(columna)) if columna else ""

    articulo = cleaner.limpiar_identificador(campo("articulo"))
    titulo = cleaner.limpiar_titulo(campo("titulo"))
    descripcion = cleaner.limpiar_html(campo("descripcion"))
    limpieza = cleaner.limpiar_html(campo("descripcion_limpieza"))
    color = cleaner.limpiar_color(campo("color"))
    familia = cleaner.limpiar_texto(campo("familia"))
    linea = cleaner.limpiar_texto(campo("linea"))
    estilo = normalizer.extraer_estilo(campo("producto_base"))
    categorias = normalizer.partir_supercategorias(campo("categorias"))
    aprobacion = cleaner.limpiar_texto(campo("aprobacion"))

    marca = normalizer.detectar_marca(titulo, descripcion, campo("categorias"))

    # Columnas del concentrado que alimentan la tabla de especificaciones.
    # Las claves son los campos lógicos de rules.BODY_ESPECIFICACIONES.
    especificaciones = {
        "acabado":           cleaner.limpiar_texto(campo("acabado")),
        "forro":             cleaner.limpiar_texto(campo("forro")),
        "construccion":      cleaner.limpiar_texto(campo("construccion")),
        "ancho":             cleaner.limpiar_texto(campo("ancho")),
        "corrida":           cleaner.limpiar_texto(campo("corrida")),
        "altura_tacon":      cleaner.limpiar_texto(campo("altura_tacon")),
        "altura_plataforma": cleaner.limpiar_texto(campo("altura_plataforma")),
        "altura_tubo":       cleaner.limpiar_texto(campo("altura_tubo")),
        "diametro_tubo":     cleaner.limpiar_texto(campo("diametro_tubo")),
        "color":             color,
        "linea":             linea,
    }

    urls = images.extraer_urls(campo("imagenes"))
    validas, invalidas = images.clasificar_urls(urls)

    producto = Producto(
        articulo=articulo,
        estilo=estilo or articulo,
        titulo=titulo,
        body_html=normalizer.construir_body_html(descripcion, limpieza,
                                                 especificaciones),
        vendor=marca,
        tipo=normalizer.determinar_type(familia, categorias),
        tags=normalizer.construir_tags(
            familia=familia, categorias=categorias, linea=linea,
            color=color, marca=marca, estilo=estilo, titulo=titulo,
        ),
        color=color,
        familia=familia,
        linea=linea,
        aprobacion=aprobacion,
        imagenes=validas,
        imagenes_invalidas=invalidas,
        articulos=[articulo],
    )

    # Estado según la aprobación del proveedor
    aprobado = aprobacion.lower() == rules.APROBACION_VALOR_OK.lower()
    if not aprobado:
        producto.problemas.append("no_aprobado")
        if rules.PRODUCTOS_NO_APROBADOS == "draft":
            producto.estatus = "draft"
            producto.publicado = "false"

    return producto


def construir_productos(df_maestro: pd.DataFrame, mapa_maestro: dict[str, str],
                        variantes_por_articulo: dict[str, list[Variante]]
                        ) -> tuple[list[Producto], list[dict]]:
    """
    Une el maestro con las variantes y devuelve la lista de productos de
    Shopify, ya con su handle único.
    """
    incidencias: list[dict] = []
    productos: list[Producto] = []
    handles_usados: set[str] = set()

    if rules.AGRUPACION == "producto_base":
        productos, incidencias = _agrupar_por_producto_base(
            df_maestro, mapa_maestro, variantes_por_articulo, handles_usados)
    else:
        for _, fila in df_maestro.iterrows():
            producto = _fila_a_producto(fila, mapa_maestro)
            if not producto.articulo:
                incidencias.append({
                    "tipo": "producto_sin_articulo",
                    "detalle": "Fila del maestro sin número de artículo; se descarta.",
                })
                continue

            producto.variantes = list(variantes_por_articulo.get(producto.articulo, []))
            for variante in producto.variantes:
                variante.color = producto.color
                variante.sku = (variante.barcode if rules.SKU_ESTRATEGIA == "ean"
                                else producto.articulo)

            deseado = normalizer.handle_deseado(producto.estilo, producto.color,
                                                producto.articulo)
            producto.handle = normalizer.construir_handle(
                producto.estilo, producto.color, producto.articulo, handles_usados)
            if producto.handle != deseado:
                producto.problemas.append("handle_duplicado")
                producto.detalles["handle_duplicado"] = (
                    f"El handle '{deseado}' ya estaba ocupado por otro artículo; "
                    f"este producto se guardó como '{producto.handle}'.")
            productos.append(producto)

    # Variantes cuyo artículo no existe en el maestro: no se pueden exportar
    # porque no tienen título, color ni imagen. Se reportan.
    articulos_maestro = {a for p in productos for a in p.articulos}
    huerfanas = {a: v for a, v in variantes_por_articulo.items()
                 if a not in articulos_maestro}
    for articulo, lista in huerfanas.items():
        incidencias.append({
            "tipo": "variantes_huerfanas",
            "articulo": articulo,
            "detalle": (f"{len(lista)} tallas con EAN y precio, pero el artículo no "
                        f"existe en la hoja '{rules.HOJA_MAESTRO}'. No se exporta "
                        f"porque no hay título, color ni imagen."),
        })

    log.info("Productos construidos: %d (agrupación='%s')", len(productos), rules.AGRUPACION)
    if huerfanas:
        log.warning("%d artículos con EAN no existen en el maestro; ver el reporte.",
                    len(huerfanas))
    return productos, incidencias


def _agrupar_por_producto_base(df_maestro, mapa_maestro, variantes_por_articulo,
                               handles_usados) -> tuple[list[Producto], list[dict]]:
    """
    Modo alternativo: un producto de Shopify por estilo, con el color como
    Option2. Sólo se agrupan filas que comparten EXACTAMENTE el mismo código
    de producto base; nunca por parecido de nombre.
    """
    incidencias: list[dict] = []
    grupos: dict[str, list[Producto]] = {}

    for _, fila in df_maestro.iterrows():
        producto = _fila_a_producto(fila, mapa_maestro)
        if not producto.articulo:
            incidencias.append({"tipo": "producto_sin_articulo",
                                "detalle": "Fila del maestro sin número de artículo."})
            continue
        grupos.setdefault(producto.estilo or producto.articulo, []).append(producto)

    productos: list[Producto] = []
    for estilo, miembros in grupos.items():
        # OJO: miembros[0] y principal son el MISMO objeto, así que hay que
        # guardar el color de cada miembro antes de vaciar el del principal.
        colores = {id(m): m.color for m in miembros}

        principal = miembros[0]
        principal.articulos = [m.articulo for m in miembros]
        principal.color = ""
        principal.variantes = []
        principal.imagenes = []
        principal.imagenes_invalidas = []

        for miembro in miembros:
            color_miembro = colores[id(miembro)]
            for variante in variantes_por_articulo.get(miembro.articulo, []):
                variante.color = color_miembro
                variante.sku = (variante.barcode if rules.SKU_ESTRATEGIA == "ean"
                                else miembro.articulo)
                principal.variantes.append(variante)
            for url in miembro.imagenes:
                if url not in principal.imagenes:
                    principal.imagenes.append(url)
            principal.imagenes_invalidas.extend(miembro.imagenes_invalidas)

        if len(principal.variantes) > rules.MAXIMO_VARIANTES_POR_PRODUCTO:
            incidencias.append({
                "tipo": "demasiadas_variantes",
                "articulo": estilo,
                "detalle": (f"{len(principal.variantes)} variantes; Shopify admite "
                            f"{rules.MAXIMO_VARIANTES_POR_PRODUCTO}."),
            })

        principal.handle = normalizer.construir_handle(
            estilo, "", principal.articulo, handles_usados)
        productos.append(principal)

    return productos, incidencias
