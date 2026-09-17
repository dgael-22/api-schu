# -*- coding: utf-8 -*-
"""
processors/normalizer.py
========================
Convierte los valores ya limpios a la forma que espera Shopify: tallas,
marcas, categorías, tags y handles.

Ninguna función de este módulo inventa datos. Cuando la información no
alcanza para decidir, devuelve vacío y quien llama registra la advertencia.
"""

from __future__ import annotations

import logging
import re

from config import rules
from utils.helpers import (
    a_decimal, es_nulo, formatear_numero_talla, sin_acentos, slug, texto,
    title_case, unicos_en_orden,
)

log = logging.getLogger("procesador.normalizador")


# ---------------------------------------------------------------------------
# Tallas
# ---------------------------------------------------------------------------

_LETRAS = {t.upper() for t in rules.TALLAS_TEXTO_LITERAL}


def normalizar_talla(valor) -> str:
    """
    El concentrado guarda las tallas de calzado en milímetros x10.
        '220' -> '22'      '225' -> '22.5'     '300' -> '30'
    Los cinturones usan su propia medida de 2 dígitos y NO se tocan:
        '32'  -> '32'
    Las tallas de letra se dejan literales:
        'UNI' -> 'UNI'     'M' -> 'M'
    """
    bruto = texto(valor).upper()
    if not bruto:
        return ""

    if bruto in _LETRAS:
        return bruto

    numero = a_decimal(bruto)
    if numero is None:
        return bruto  # algo como '4-6 AÑOS': se respeta tal cual

    if rules.TALLA_DIVIDIR_ENTRE_10:
        minimo, maximo = rules.TALLA_RANGO_CALZADO
        entero = int(numero) if numero == int(numero) else None
        if (entero is not None
                and minimo <= entero <= maximo
                and len(str(entero)) >= 3
                and entero % rules.TALLA_MULTIPLO == 0):
            return formatear_numero_talla(entero / 10.0)

    return formatear_numero_talla(numero)


def clave_orden_talla(talla: str):
    """Ordena tallas: primero las numéricas de menor a mayor, luego las de letra."""
    valor = texto(talla).upper()
    numero = a_decimal(valor)
    if numero is not None:
        return (0, numero, "")
    if valor in rules.ORDEN_TALLAS_LETRA:
        return (1, rules.ORDEN_TALLAS_LETRA.index(valor), valor)
    return (2, 0, valor)


# ---------------------------------------------------------------------------
# Marca / Vendor
# ---------------------------------------------------------------------------

def detectar_marca(*fuentes) -> str:
    """
    El concentrado no trae columna de marca: se busca en el título, la
    descripción y las categorías. Si no aparece ninguna marca conocida,
    devuelve VENDOR_POR_DEFECTO (vacío). Nunca se adivina.
    """
    texto_junto = " ".join(texto(f) for f in fuentes).lower()
    if not texto_junto.strip():
        return rules.VENDOR_POR_DEFECTO

    for marca in rules.ORDEN_DETECCION_MARCAS:
        for palabra in rules.MARCAS_CONOCIDAS.get(marca, []):
            if palabra.lower() in texto_junto:
                return marca
    return rules.VENDOR_POR_DEFECTO


def normalizar_marca(valor) -> str:
    """'  NIKE  ' / 'nike' -> el nombre canónico si está en el diccionario."""
    limpio = texto(valor)
    if not limpio:
        return ""
    return rules.MARCAS_NORMALIZADAS.get(limpio.lower(), title_case(limpio))


# ---------------------------------------------------------------------------
# Categorías de Hybris
# ---------------------------------------------------------------------------

def partir_supercategorias(valor) -> list[str]:
    """
    'Dama:Staged:flexiProductCatalog,Dama_Sneakers:Staged:...'
        -> ['Dama', 'Dama_Sneakers']
    """
    bruto = texto(valor)
    if not bruto:
        return []
    partes = []
    for trozo in bruto.split(","):
        codigo = trozo.split(":")[0].strip()
        if codigo:
            partes.append(codigo)
    return unicos_en_orden(partes)


def detectar_genero(categorias: list[str]) -> str | None:
    """Devuelve 'dama' | 'caballero' | 'ninos' | None a partir de las categorías."""
    presentes = {c.lower() for c in categorias}
    for clave in rules.ORDEN_DETECCION_GENERO:
        if clave.lower() in presentes:
            return rules.GENERO_POR_CATEGORIA[clave]
    return None


def determinar_type(familia: str, categorias: list[str]) -> str:
    """
    Type de Shopify a partir de la Familia (CALZADO/ACCESORIOS) y el género.
    Si no hay información suficiente devuelve TYPE_POR_DEFECTO.
    """
    familia_norm = sin_acentos(texto(familia)).upper()
    genero = detectar_genero(categorias)

    if familia_norm == rules.FAMILIA_CALZADO:
        return rules.TYPE_CALZADO.get(genero, rules.TYPE_CALZADO[None])
    if familia_norm == rules.FAMILIA_ACCESORIOS:
        return rules.TYPE_ACCESORIOS.get(genero, rules.TYPE_ACCESORIOS[None])
    return rules.TYPE_POR_DEFECTO


def categoria_por_titulo(titulo: str) -> str:
    """Categoría legible deducida de palabras del propio título. Sólo para tags."""
    base = sin_acentos(texto(titulo)).lower()
    for etiqueta, palabras in rules.PALABRAS_CATEGORIA.items():
        for palabra in palabras:
            if sin_acentos(palabra).lower() in base:
                return etiqueta
    return ""


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

_GENERO_ETIQUETA = {"dama": "Dama", "caballero": "Caballero", "ninos": "Niños"}


def _es_segmento_estructural(segmento: str) -> bool:
    """¿Este trozo de la ruta es familia, género o marca, y no una categoría?"""
    return sin_acentos(segmento).strip().lower() in {
        sin_acentos(s).lower() for s in rules.TAGS_SEGMENTOS_ESTRUCTURALES
    }


def _es_segmento_marca(segmento: str) -> bool:
    """¿Este trozo es el nombre de una marca?"""
    return sin_acentos(segmento).strip().lower() in {
        sin_acentos(s).lower() for s in rules.TAGS_SEGMENTOS_MARCA
    }


def _tag_legible(codigo: str) -> str:
    """
    Convierte la ruta de supercategoría de Hybris en un tag legible, quitando
    TODOS los segmentos estructurales del principio y del final:

        Accesorios_Caballero_Cinturones -> 'Cinturones'
        Dama_Botas_Botines              -> 'Botas Botines'
        New_Arrivals_Dama               -> 'New Arrivals'
        Accesorios_Caballero            -> ''  (no queda categoría; se descarta)

    Antes sólo se quitaba el primer segmento, y por eso salían tags como
    'Caballero Cinturones' que repetían el tag de género.
    """
    partes = [p for p in codigo.split("_") if p.strip()]

    # Familia y género se quitan de los dos extremos.
    while partes and _es_segmento_estructural(partes[0]):
        partes = partes[1:]
    while partes and _es_segmento_estructural(partes[-1]):
        partes = partes[:-1]

    # Marcas: fuera del final siempre; del inicio sólo si no queda categoría.
    while partes and _es_segmento_marca(partes[-1]):
        partes = partes[:-1]
    if partes and all(_es_segmento_marca(p) for p in partes):
        return ""

    if not partes:
        return ""
    return title_case(" ".join(partes).replace("_", " "))


def _clave_tag(tag: str) -> str:
    """
    Llave para detectar tags equivalentes: sin acentos, en minúsculas y sin la
    's' final, para que 'Café'/'Cafe' y 'Plantilla'/'Plantillas' sean el mismo.
    """
    base = sin_acentos(tag).lower().strip()
    base = " ".join(base.split())
    if rules.TAGS_UNIFICAR_SINGULAR_PLURAL and len(base) > 3 and base.endswith("s"):
        base = base[:-1]
    return base


def _canonizar_tag(tag: str) -> str:
    """Aplica la tabla de formas canónicas de rules.TAGS_CANONICOS."""
    clave = " ".join(sin_acentos(tag).lower().split())
    return rules.TAGS_CANONICOS.get(clave, tag)


def _depurar_tags(tags: list[str]) -> list[str]:
    """
    Quita vacíos, unifica formas canónicas y colapsa equivalentes
    (singular/plural, con y sin acento). Gana la primera forma que aparece.
    """
    resultado: list[str] = []
    vistos: dict[str, int] = {}

    for bruto in tags:
        tag = _canonizar_tag((bruto or "").strip())
        if not tag:
            continue
        clave = _clave_tag(tag)
        if not clave:
            continue
        if clave in vistos:
            # Si la nueva forma trae acento y la guardada no, se prefiere la
            # acentuada: 'Café' se lee mejor que 'Cafe'.
            indice = vistos[clave]
            if sin_acentos(resultado[indice]) == resultado[indice] and \
               sin_acentos(tag) != tag:
                resultado[indice] = tag
            continue
        vistos[clave] = len(resultado)
        resultado.append(tag)

    if rules.TAGS_MAXIMO:
        resultado = resultado[: rules.TAGS_MAXIMO]
    return resultado


def construir_tags(*, familia: str, categorias: list[str], linea: str,
                   color: str, marca: str, estilo: str, titulo: str) -> str:
    """
    Arma la cadena de tags con datos reales del concentrado. Los códigos
    internos de Hybris (aesth1, vig, stock_a, sales_d...) se descartan.
    """
    tags: list[str] = []

    if rules.TAGS_INCLUIR_MARCA and marca:
        tags.append(marca)

    if rules.TAGS_INCLUIR_FAMILIA and familia:
        tags.append(title_case(familia))

    genero = detectar_genero(categorias)
    if rules.TAGS_INCLUIR_GENERO and genero:
        tags.append(_GENERO_ETIQUETA[genero])

    if rules.TAGS_INCLUIR_CATEGORIAS:
        for codigo in categorias:
            bajo = codigo.lower()
            if bajo in rules.TAGS_EXACTOS_DESCARTADOS:
                continue
            if bajo.startswith(rules.TAGS_PREFIJOS_DESCARTADOS):
                continue
            if codigo in rules.GENERO_POR_CATEGORIA:
                continue
            legible = _tag_legible(codigo)
            if legible:
                tags.append(legible)

    if rules.TAGS_INCLUIR_LINEA and linea:
        tags.append(title_case(linea))

    if rules.TAGS_INCLUIR_COLOR and color:
        tags.append(title_case(color))

    categoria = categoria_por_titulo(titulo)
    if categoria:
        tags.append(categoria)

    if rules.TAGS_INCLUIR_ESTILO and estilo:
        tags.append(estilo)

    limpios = _depurar_tags(list(unicos_en_orden(t.strip() for t in tags if t and t.strip())))

    if getattr(rules, "TAGS_SOLO_VOCABULARIO", False):
        # Con el vocabulario cerrado encendido, los tags se reparten en sus
        # clases y salen en el orden de rules.TAGS_ORDEN_CLASES. Lo que no
        # está en el vocabulario no se escribe.
        return construir_tags_vocabulario(limpios, titulo)[0]

    return ", ".join(sorted(limpios, key=lambda s: sin_acentos(s).lower()))


def construir_tags_vocabulario(tags: list[str], titulo: str,
                               extra: list[str] | None = None):
    """
    Pasa los tags por el vocabulario cerrado de `config/rules.py`.

    Devuelve `(cadena_de_tags, clasificacion)`. La clasificación trae lo que se
    descartó y por qué, lo que no se reconoció, y si el producto quedó con dos
    siluetas en conflicto — en ese caso NO se elige una: se marca para que lo
    revise una persona, igual que los mapeos sin confirmar del ETS.
    """
    from processors import vocabulario

    clasificacion = vocabulario.clasificar(tags, titulo, extra)
    return ", ".join(clasificacion.tags), clasificacion


# ---------------------------------------------------------------------------
# Estilo y handle
# ---------------------------------------------------------------------------

def extraer_estilo(producto_base) -> str:
    """'136707:Staged:flexiProductCatalog' -> '136707'"""
    bruto = texto(producto_base)
    if not bruto:
        return ""
    return bruto.split(":")[0].strip()


def handle_deseado(estilo: str, color: str, articulo: str) -> str:
    """El handle que le tocaría al producto si nadie más lo hubiera ocupado."""
    base = rules.HANDLE_PATRON.format(estilo=slug(estilo), color=slug(color))
    base = re.sub(r"-{2,}", "-", base).strip("-")
    if not base:
        base = slug(articulo)
    return base[:rules.HANDLE_MAXIMO]


def construir_handle(estilo: str, color: str, articulo: str, usados: set[str]) -> str:
    """
    Handle único con el patrón de la plantilla ('88602-negro').
    Si dos artículos distintos generan el mismo handle, se añade el número de
    artículo como sufijo en lugar de perder uno de los dos productos.
    """
    base = handle_deseado(estilo, color, articulo)

    if base not in usados:
        usados.add(base)
        return base

    if rules.HANDLE_SUFIJO_EN_COLISION == "articulo":
        candidato = f"{base}-{slug(articulo)}"[:rules.HANDLE_MAXIMO]
        if candidato not in usados:
            usados.add(candidato)
            return candidato

    contador = 2
    while f"{base}-{contador}" in usados:
        contador += 1
    candidato = f"{base}-{contador}"
    usados.add(candidato)
    return candidato


# ---------------------------------------------------------------------------
# Cuerpo HTML
# ---------------------------------------------------------------------------

def _valor_especificacion(campo: str, valor: str) -> str:
    """Limpia y formatea un valor de la tabla de especificaciones."""
    bruto = texto(valor)
    if not bruto:
        return ""

    bruto = rules.BODY_VALORES_CORREGIDOS.get(bruto.upper(), bruto)

    if rules.BODY_NORMALIZAR_VALORES == "titulo":
        bruto = title_case(bruto)

    if campo in rules.BODY_CAMPOS_MEDIDA and rules.UNIDAD_MEDIDA:
        bruto = f"{bruto} {rules.UNIDAD_MEDIDA}"

    return bruto


def construir_especificaciones(datos: dict[str, str]) -> list[tuple[str, str]]:
    """
    Devuelve [(etiqueta, valor)] con las especificaciones que el producto SÍ
    tiene, en el orden de rules.BODY_ESPECIFICACIONES.

    Los campos sin dato no aparecen: no se escribe "No disponible" ni ningún
    relleno. Si el proveedor no lo mandó, la fila no existe.
    """
    filas: list[tuple[str, str]] = []
    for campo, etiqueta in rules.BODY_ESPECIFICACIONES:
        valor = _valor_especificacion(campo, datos.get(campo, ""))
        if valor:
            filas.append((etiqueta, valor))
    return filas


def _escapar(valor: str) -> str:
    return (str(valor).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def construir_body_html(descripcion: str, limpieza: str = "",
                        especificaciones: dict[str, str] | None = None) -> str:
    """
    Arma la descripción del producto en secciones:

        <h3>Acerca del producto</h3>   el texto del proveedor, tal cual
        <h3>Especificaciones</h3>      tabla de materiales y medidas
        <h3>Cuidado y limpieza</h3>    las instrucciones del proveedor

    Cada sección sólo aparece si tiene contenido. Nada se inventa: los valores
    salen de las columnas del concentrado y los campos vacíos se omiten.
    """
    descripcion = texto(descripcion)
    limpieza = texto(limpieza)
    filas = (construir_especificaciones(especificaciones or {})
             if rules.BODY_INCLUIR_ESPECIFICACIONES else [])

    partes: list[str] = []

    if descripcion:
        cuerpo = (descripcion if "<" in descripcion and ">" in descripcion
                  else f"<p>{descripcion}</p>")
        if rules.BODY_TITULO_DESCRIPCION:
            partes.append(f"<h3>{_escapar(rules.BODY_TITULO_DESCRIPCION)}</h3>")
        partes.append(cuerpo)

    if filas:
        if rules.BODY_TITULO_ESPECIFICACIONES:
            partes.append(f"<h3>{_escapar(rules.BODY_TITULO_ESPECIFICACIONES)}</h3>")
        celdas = "".join(
            f"<tr><th>{_escapar(etiqueta)}</th><td>{_escapar(valor)}</td></tr>"
            for etiqueta, valor in filas
        )
        partes.append(f"<table><tbody>{celdas}</tbody></table>")

    if limpieza and rules.BODY_INCLUIR_LIMPIEZA:
        if rules.BODY_TITULO_LIMPIEZA:
            partes.append(f"<h3>{_escapar(rules.BODY_TITULO_LIMPIEZA)}</h3>")
        partes.append(limpieza if "<" in limpieza and ">" in limpieza
                      else f"<p>{limpieza}</p>")

    return "".join(partes)
