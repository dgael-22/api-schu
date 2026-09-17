# -*- coding: utf-8 -*-
"""
config/rules.py
===============
Todas las reglas que probablemente cambien al recibir otro concentrado o al
dar de alta un proveedor nuevo viven AQUÍ. El código de processors/ no
contiene ninguna regla de negocio: sólo la aplica.

Si mañana llega un Excel con otras columnas, en la mayoría de los casos basta
con añadir el alias en COLUMN_ALIASES y no tocar nada más.
"""

# ---------------------------------------------------------------------------
# 1. ARCHIVOS
# ---------------------------------------------------------------------------

ARCHIVO_ORIGEN = "concentrado fp(2).xlsx"
# La plantilla puede venir como .xlsx o .csv; se busca en este orden.
ARCHIVO_PLANTILLA = ["products_export_1 (1).xlsx", "products_export_1 (1).csv"]

ARCHIVO_SALIDA = "products_export_limpio.xlsx"
ARCHIVO_REPORTE = "reporte_proceso.xlsx"

# Además del .xlsx se puede generar un .csv UTF-8, que es lo que Shopify
# importa de forma nativa. Poner en False si no se quiere.
GENERAR_CSV_SHOPIFY = True
ARCHIVO_SALIDA_CSV = "products_export_limpio.csv"

# ---------------------------------------------------------------------------
# 2. HOJAS DEL CONCENTRADO
# ---------------------------------------------------------------------------
# El concentrado es un export de SAP Hybris: trae hojas de metadatos que no
# son productos. Sólo se leen las que se listan aquí.

HOJA_MAESTRO = "FlexiVariantProductColor"

# En la hoja maestro, las 2 primeras filas debajo del encabezado son
# metadatos del export (ReferenceFormat y la etiqueta "Links Fotografías"),
# no productos. Se saltan.
MAESTRO_FILAS_METADATOS = 2

# Hojas de variantes (talla + EAN + precio). Se concatenan.
HOJAS_VARIANTES = ["CALZADO EANS Y PRECIOS", "ACCESORIOS EANS Y PRECIOS"]

# Hojas que se ignoran explícitamente (documentado para que se sepa por qué).
HOJAS_IGNORADAS = {
    "TypeTemplate": "plantilla vacía del export de Hybris",
    "TypeSystem": "definición de tipos de Hybris, no productos",
    "ClassificationTypeSystem": "definición de clasificaciones, no productos",
    "HeaderPrompt": "ayuda de encabezados del export, no productos",
}

# Columnas del maestro que vienen sin encabezado en el Excel original
# (openpyxl las nombra "Unnamed: N"). Se renombran por posición.
MAESTRO_COLUMNAS_SIN_NOMBRE = {
    "Unnamed: 26": "Links Fotografías",
    "Unnamed: 27": "Familia",
}

# ---------------------------------------------------------------------------
# 3. EQUIVALENCIAS DE COLUMNAS
# ---------------------------------------------------------------------------
# Campo lógico -> lista de nombres que ese campo puede tener en el archivo del
# proveedor. La detección es tolerante a mayúsculas, acentos y espacios.
# Sólo se incluyen equivalencias que tienen sentido para archivos de este tipo.

COLUMN_ALIASES = {
    # --- hoja maestro (producto-color) ---
    "articulo": [
        "Número de artículo*^", "Numero de articulo", "Número de artículo",
        "Prod.SAP", "Codigo SAP", "Código SAP", "SKU", "Clave",
    ],
    "producto_base": [
        "Producto base*", "Producto base", "Estilo", "Modelo", "Código producto",
    ],
    "titulo": [
        "Identificador[es]", "Identificador", "Descripcion Esp",
        "Descripción", "Descripcion", "Nombre", "Nombre producto", "Producto",
        "Artículo", "Articulo",
    ],
    "descripcion": [
        "Descripción[es]", "Descripcion[es]", "Descripción larga",
        "Descripción", "Descripcion",
    ],
    "descripcion_limpieza": ["Descripción Limpieza[es]", "Descripcion Limpieza"],
    "color": ["Color SAP[es]", "Color SAP", "Color", "Color[es]"],
    "linea": ["Nombre de línea[es]", "Nombre de linea", "Línea comercial"],
    "codigo_linea": ["Línea[es]", "Linea[es]", "Línea", "Linea"],
    "categorias": ["Supercategorías+", "Supercategorias+", "Supercategorías", "Categoría", "Categoria"],
    "familia": ["Familia", "Tipo de producto", "Division", "División"],
    "imagenes": [
        "Links Fotografías", "Links Fotografias", "Links Fotografía",
        "Imágenes", "Imagenes", "Fotos", "Imagen", "URL Imagen",
    ],
    "imagenes_galeria": ["Imágenes de la galería+", "Imagenes de la galeria+"],
    "aprobacion": ["Aprobación", "Aprobacion", "Estatus", "Status"],
    "ancho": ["Ancho[es]", "Ancho"],
    "corrida": ["Corrida MEX", "Corrida"],
    "construccion": ["Construcción[es]", "Construccion[es]", "Construcción"],
    "forro": ["Forro[es]", "Forro"],
    "acabado": ["Acabado[es]", "Acabado", "Material"],
    "altura_tacon": ["Altura Tacón[es]", "Altura Tacon"],
    "altura_plataforma": ["Altura Media Plataforma[es]"],
    "altura_tubo": ["Altura Tubo Bota[es]"],
    "diametro_tubo": ["Diámetro Tubo Bota[es]", "Diametro Tubo Bota[es]"],
    "material_limpieza": ["Material para limpieza"],

    # --- hojas de variantes (talla + EAN + precio) ---
    "var_articulo": ["Prod.SAP", "Prod SAP", "Codigo SAP", "Código SAP", "Artículo", "Clave", "Referencia"],
    "var_descripcion": ["Descripcion Esp", "Descripción Esp", "Descripcion", "Descripción"],
    "var_talla": ["Talla", "Tallas", "Size", "Medida"],
    "var_ean": ["Cod EAN/UPC", "EAN", "UPC", "Código de barras", "Codigo de barras", "Barcode"],
    "var_precio": ["$ FULL", "$FULL", "Precio", "Precio Venta", "Precio Publico", "Precio Público", "PVP"],
}

# Campos que el proceso NO puede continuar sin ellos.
CAMPOS_OBLIGATORIOS_MAESTRO = ["articulo", "titulo"]
CAMPOS_OBLIGATORIOS_VARIANTES = ["var_articulo", "var_talla", "var_precio"]

# ---------------------------------------------------------------------------
# 4. AGRUPACIÓN DE PRODUCTOS Y VARIANTES
# ---------------------------------------------------------------------------
# "articulo"       -> 1 producto de Shopify por cada estilo+color
#                     (Option1 = Talla). Es como están los productos
#                     Flexi/Quirelli que ya existen en la plantilla.
# "producto_base"  -> 1 producto por estilo, con Option1 = Talla y
#                     Option2 = Color. Menos fichas, más riesgo de mezclar.
AGRUPACION = "articulo"

OPTION1_NAME = "Talla"
OPTION2_NAME = "Color"     # sólo se usa si AGRUPACION == "producto_base"

# Orden de las tallas dentro de un producto: numéricas de menor a mayor y
# después las de letra en este orden.
ORDEN_TALLAS_LETRA = ["XS", "S", "M", "L", "XL", "XXL", "UNI", "OS"]

# ---------------------------------------------------------------------------
# 5. TALLAS
# ---------------------------------------------------------------------------
# El concentrado guarda las tallas de calzado en milímetros x10:
#   220 -> 22   225 -> 22.5   300 -> 30
# Pero los cinturones usan su propia medida de 2 dígitos (32, 34 ... 44) y
# NO deben dividirse. Regla conservadora: sólo se divide entre 10 cuando el
# valor tiene 3 dígitos, es múltiplo de 5 y cae en el rango de calzado.
TALLA_DIVIDIR_ENTRE_10 = True
TALLA_RANGO_CALZADO = (130, 450)    # 13.0 a 45.0
TALLA_MULTIPLO = 5                  # sólo enteros y medios puntos

# Tallas que se dejan exactamente como vienen.
TALLAS_TEXTO_LITERAL = ["UNI", "OS", "XS", "S", "M", "L", "XL", "XXL", "U", "N/A"]

# ---------------------------------------------------------------------------
# 6. MARCAS
# ---------------------------------------------------------------------------
# El concentrado no trae columna de marca: se detecta buscando estas palabras
# en el título, la descripción y las categorías. Si no se detecta ninguna,
# el Vendor queda VACÍO y se registra una advertencia. Nunca se inventa.
MARCAS_CONOCIDAS = {
    "Quirelli": ["quirelli"],
    "Flexi":    ["flexi"],
}
# Se evalúan en este orden: la primera que coincida gana. "Quirelli" va antes
# porque sus descripciones también mencionan al grupo Flexi.
ORDEN_DETECCION_MARCAS = ["Quirelli", "Flexi"]

VENDOR_POR_DEFECTO = ""   # vacío a propósito: no inventar marca

# Normalización de marcas escritas de cualquier forma.
MARCAS_NORMALIZADAS = {
    "flexi": "Flexi",
    "quirelli": "Quirelli",
}

# ---------------------------------------------------------------------------
# 7. CATEGORÍAS / TYPE
# ---------------------------------------------------------------------------
# El campo Type de la plantilla usa estos valores reales:
#   calzado-dama, calzado-caballero, calzado-ninos, calzado, accesorios, otros
# Se decide con la Familia (CALZADO / ACCESORIOS) + el género que venga en
# Supercategorías. NO se inventa: si no hay información, queda "otros".

FAMILIA_CALZADO = "CALZADO"
FAMILIA_ACCESORIOS = "ACCESORIOS"

# Palabra que aparece en Supercategorías -> género
GENERO_POR_CATEGORIA = {
    "Ninos_Nina": "ninos",
    "Ninos_Nino": "ninos",
    "Ninos": "ninos",
    "Dama": "dama",
    "Caballero": "caballero",
}
ORDEN_DETECCION_GENERO = ["Ninos_Nina", "Ninos_Nino", "Ninos", "Dama", "Caballero"]

TYPE_CALZADO = {
    "dama": "calzado-dama",
    "caballero": "calzado-caballero",
    "ninos": "calzado-ninos",
    None: "calzado",
}
TYPE_ACCESORIOS = {
    "dama": "accesorios",
    "caballero": "accesorios",
    "ninos": "accesorios",
    None: "accesorios",
}
TYPE_POR_DEFECTO = "otros"

# Palabras del título que refinan la categoría cuando existen. Se usan sólo
# para TAGS, nunca para inventar un Type que los datos no soporten.
PALABRAS_CATEGORIA = {
    "Tenis": ["tenis", "sneaker"],
    "Botas": ["bota "],
    "Botines": ["botin", "botín"],
    "Sandalias": ["sandalia", "huarache"],
    "Zapatos": ["zapato", "oxford", "choclo"],
    "Mocasines": ["mocasin", "mocasín"],
    "Balerinas": ["balerina", "flat"],
    "Zuecos": ["zueco"],
    "Cinturones": ["cinturon", "cinturón"],
    "Calcetines": ["calcetin", "calcetín"],
    "Plantillas": ["plantilla"],
    "Bolsas": ["bolsa", "mochila"],
    "Carteras": ["cartera", "billetera", "monedero", "tarjetero"],
    "Cuidado del calzado": ["crema", "cera", "cepillo", "limpiador", "grasa", "tinta"],
    "Agujetas": ["agujeta"],
    "Gorras": ["gorra"],
}

# `Product Category` es la taxonomía oficial de Shopify. El concentrado no la
# trae y no se puede deducir con seguridad, así que se deja vacía.
PRODUCT_CATEGORY_POR_DEFECTO = ""

# ---------------------------------------------------------------------------
# 8. TAGS
# ---------------------------------------------------------------------------
# Las supercategorías de Hybris traen códigos internos que no sirven como tag
# de tienda. Se descartan por prefijo o por coincidencia exacta.
TAGS_PREFIJOS_DESCARTADOS = ("aesth", "sales_", "stock_", "vig", "fxi", "cps_", "cu_")
TAGS_EXACTOS_DESCARTADOS = {"fotos", "vig", "pretemporada", "ofertas_45_dcto", "live_shopping"}

# Cómo se arma la lista de tags de cada producto.
TAGS_INCLUIR_FAMILIA = True      # CALZADO / ACCESORIOS -> "Calzado" / "Accesorios"
TAGS_INCLUIR_GENERO = True       # Dama / Caballero / Niños
TAGS_INCLUIR_CATEGORIAS = True   # Sneakers, Botines, Cinturones... (de Supercategorías)
TAGS_INCLUIR_LINEA = True        # Nombre de línea comercial (ANANSA, ARCHER...)
TAGS_INCLUIR_COLOR = True
TAGS_INCLUIR_MARCA = True
# El código de estilo dejó de escribirse como tag: en la tienda real generaba
# ~950 tags que aplicaban a 4 productos cada uno, y el cliente los veía en el
# filtro lateral. Para buscar en el admin ya está el SKU de la variante.
TAGS_INCLUIR_ESTILO = False

# ---------------------------------------------------------------------------
# 9. PRECIOS
# ---------------------------------------------------------------------------
PRECIO_DECIMALES = 2
PRECIO_SEPARADOR_DECIMAL = "."
# Caracteres que se eliminan antes de convertir a número: $ , espacios, MXN...
# Ojo: la coma NO se lista aquí. La decide utils.helpers.a_decimal, que
# distingue si es separador de miles (1,299) o decimal (1.299,00).
PRECIO_CARACTERES_BASURA = ["$", " ", "\u00a0", "MXN", "mxn", "M.N.", "pesos"]
PRECIO_MINIMO_VALIDO = 0.01
PRECIO_MAXIMO_VALIDO = 1_000_000.0

# ---------------------------------------------------------------------------
# 10. SKU Y CÓDIGO DE BARRAS
# ---------------------------------------------------------------------------
# "sap" -> Variant SKU = número de artículo SAP (mismo para todas las tallas
#          del producto). Es la convención que ya usan los productos
#          Flexi/Quirelli cargados en la tienda.
# "ean" -> Variant SKU = EAN de cada talla (único por variante).
SKU_ESTRATEGIA = "sap"

USAR_EAN_COMO_BARCODE = True

# El export de Shopify que sirve de plantilla trae los SKU con un apóstrofo
# delante ('1390014023). Ese apóstrofo lo añade Excel al abrir el CSV: NO es
# parte del dato. Se escribe la celda como texto para conservar los ceros a la
# izquierda sin necesidad del apóstrofo. Poner en True sólo si se quiere
# reproducir el archivo tal cual, con apóstrofo incluido.
SKU_PREFIJO_APOSTROFO = False

# Columnas que deben escribirse SIEMPRE como texto para no perder ceros
# iniciales ni convertirse a notación científica.
COLUMNAS_TEXTO = ["Variant SKU", "Variant Barcode", "Option1 Value",
                  "Option2 Value", "Option3 Value", "Handle"]

# ---------------------------------------------------------------------------
# 11. IMÁGENES
# ---------------------------------------------------------------------------
IMAGEN_SEPARADORES = [",", ";", "|", "\n"]
IMAGEN_EXTENSIONES_VALIDAS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]
IMAGEN_MAXIMO_POR_PRODUCTO = 250        # límite de Shopify
IMAGEN_ALT_TEXT = ""                    # vacío: no inventar textos alternativos

# Validación de URLs por red. Está APAGADA por defecto: el proceso no debe
# depender de internet. Se puede encender desde la línea de comandos con
#   python main.py --validar-imagenes
VALIDAR_URLS_IMAGENES = False
IMAGEN_TIMEOUT_SEGUNDOS = 5
IMAGEN_HILOS = 8
IMAGEN_MAXIMO_A_VALIDAR = 0             # 0 = todas

# ---------------------------------------------------------------------------
# 12. LIMPIEZA DE TEXTO
# ---------------------------------------------------------------------------
LIMPIAR_ESPACIOS_DOBLES = True
LIMPIAR_SALTOS_DE_LINEA = True
LIMPIAR_MOJIBAKE = True

# Correcciones de codificación detectadas en el archivo real (CAFÉ mal
# codificado). Se aplican tal cual, sin adivinar.
CORRECCIONES_MOJIBAKE = {
    "�": "É",          # carácter de reemplazo dentro de CAFÉ / NEGRO CAFÉ
    "Ã©": "é", "Ã³": "ó", "Ã­": "í", "Ã¡": "á", "Ãº": "ú", "Ã±": "ñ",
    "Ã‰": "É", "Ã“": "Ó", "Ã": "Í", "Ã": "Á", "Ãš": "Ú", "Ã‘": "Ñ",
}

# Valores que significan "vacío" aunque no lo estén.
VALORES_NULOS = ["", "nan", "NaN", "None", "null", "NULL", "N/A", "n/a",
                 "#N/A", "-", "--", "SIN DATO", "SIN CLASIFICAR"]

# El título ya viene en formato correcto en Identificador[es]. Poner en
# "titulo" para forzar Title Case, "ninguno" para no tocarlo.
NORMALIZAR_TITULO = "ninguno"
# El color SAP viene en MAYÚSCULAS; para los tags queda mejor en Título.
NORMALIZAR_COLOR = "titulo"

# Palabras que NUNCA cambian de forma al aplicar Title Case.
PALABRAS_INTACTAS = ["Flexi", "Quirelli", "MEX", "UNI", "XS", "S", "M", "L",
                     "XL", "XXL", "EE", "EEE", "PV", "OI", "2X", "3X"]
PALABRAS_MINUSCULAS = ["de", "del", "la", "el", "los", "las", "y", "con",
                       "para", "en", "por", "a", "al", "un", "una", "sin"]


# ---------------------------------------------------------------------------
# 12.b DESCRIPCIÓN DEL PRODUCTO (Body HTML)
# ---------------------------------------------------------------------------
# El Body se arma en secciones. Cambia aquí los títulos, el orden o las
# etiquetas sin tocar el código.

BODY_INCLUIR_ESPECIFICACIONES = True
BODY_INCLUIR_LIMPIEZA = True

BODY_TITULO_DESCRIPCION = "Acerca del producto"
BODY_TITULO_ESPECIFICACIONES = "Especificaciones"
BODY_TITULO_LIMPIEZA = "Cuidado y limpieza"

# Campo lógico -> etiqueta que ve el cliente. El orden de esta lista es el
# orden en que salen las filas.
#
# REGLA: sólo se escribe la fila si el producto TIENE ese dato. Nunca se pone
# "No disponible", "N/A" ni nada parecido: si el proveedor no lo mandó, la fila
# simplemente no existe.
BODY_ESPECIFICACIONES = [
    ("acabado",           "Material exterior"),
    ("forro",             "Forro"),
    ("construccion",      "Construcción"),
    ("ancho",             "Ancho"),
    ("altura_tacon",      "Altura de tacón"),
    ("altura_plataforma", "Altura de plataforma"),
    ("altura_tubo",       "Altura del tubo"),
    ("diametro_tubo",     "Diámetro del tubo"),
]

# Campos que SE QUITARON de la tabla por redundantes. Se dejan documentados
# para poder devolverlos con sólo moverlos a la lista de arriba:
#   ("corrida", "Corrida de tallas")  la talla ya es la variante (Option1)
#   ("color",   "Color")              el color ya está en el título y en los tags
#   ("linea",   "Línea")              la línea ya está en los tags
BODY_ESPECIFICACIONES_RETIRADAS = [
    ("corrida",           "Corrida de tallas"),
    ("color",             "Color"),
    ("linea",             "Línea"),
]

# Campos que son medidas. El concentrado los manda como número pelón ("4.9")
# sin decir la unidad.
BODY_CAMPOS_MEDIDA = {"altura_tacon", "altura_plataforma",
                      "altura_tubo", "diametro_tubo"}
# Vacío a propósito: no se inventa la unidad. Cuando el proveedor confirme que
# son centímetros, pon "cm" aquí y todas las medidas saldrán como "4.9 cm".
UNIDAD_MEDIDA = ""

# Valores que el proveedor escribe de forma confusa.
BODY_VALORES_CORREGIDOS = {
    "SIN": "Sin forro",
    "SIN FORRO": "Sin forro",
}

# Los valores vienen en MAYÚSCULAS ("PIEL VACUNO"). En la tienda se leen mejor
# en formato título. "ninguno" los deja tal cual.
BODY_NORMALIZAR_VALORES = "titulo"

# ---------------------------------------------------------------------------
# 13. VALORES FIJOS DE LA PLANTILLA SHOPIFY
# ---------------------------------------------------------------------------
# Todos estos valores se tomaron de lo que realmente traen los productos
# Flexi/Quirelli de products_export_1 (1). No son invenciones.
DEFAULTS_SHOPIFY = {
    "Published": "true",
    "Status": "active",
    "Gift Card": "false",
    "Variant Inventory Tracker": "shopify",
    "Variant Inventory Policy": "deny",
    "Variant Fulfillment Service": "manual",
    "Variant Requires Shipping": "true",
    "Variant Taxable": "true",
    "Variant Grams": "0.0",
    "Variant Weight Unit": "kg",
}

# El concentrado NO trae inventario. Se escribe 0 y cada producto queda
# marcado en el reporte como "sin dato de inventario".
# Cantidad que se escribe en "Variant Inventory Qty".
# Vacío a propósito: el concentrado no trae existencias y, con el rastreo
# apagado (ver abajo), Shopify ni siquiera lee esta columna. Poner un número
# aquí sería inventar un dato. Si algún día cargas existencias reales,
# enciende INVENTARIO_RASTREADO y pon la cantidad que corresponda.
INVENTARIO_POR_DEFECTO = ""

# ¿Shopify debe LLEVAR LA CUENTA del inventario de estas variantes?
#
#   False -> la columna "Variant Inventory Tracker" se deja VACÍA. Shopify no
#            rastrea el inventario: la cantidad nunca baja aunque compren, el
#            producto siempre se puede comprar y "Variant Inventory Qty" pasa a
#            ser informativo. Es la única forma de que el número no cambie.
#
#   True  -> la columna dice "shopify". Shopify descuenta en cada venta, así que
#            una cantidad de 1 se vuelve 0 con la primera compra. Úsalo cuando
#            de verdad vayas a cargar existencias reales.
#
# OJO: esto no se puede forzar desde el Excel. Con el rastreo encendido, quien
# decide el número es Shopify, no este archivo.
INVENTARIO_RASTREADO = False

# Qué hacer con los productos cuya Aprobación no es "approved".
# "active"   -> se exportan publicados igual que el resto (sólo se avisa)
# "draft"    -> se exportan con Status=draft y Published=false
# "excluir"  -> no se exportan; quedan listados en el reporte
APROBACION_VALOR_OK = "approved"
PRODUCTOS_NO_APROBADOS = "active"

# Columnas que se dejan vacías porque el concentrado no tiene equivalente.
# Documentado a propósito para que quede claro que no se inventaron.
COLUMNAS_SIN_ORIGEN = [
    "Product Category", "Variant Compare At Price", "Cost per item",
    "SEO Title", "SEO Description", "Image Alt Text", "Variant Image",
    "Variant Tax Code", "Option1 Linked To", "Option2 Linked To",
    "Option3 Linked To", "Unit Price Total Measure",
    "Unit Price Total Measure Unit", "Unit Price Base Measure",
    "Unit Price Base Measure Unit",
]

# ---------------------------------------------------------------------------
# 14. HANDLE
# ---------------------------------------------------------------------------
# El handle es la URL del producto. La plantilla usa "estilo-color"
# (ej. 88602-negro). Debe ser único: si dos artículos distintos generan el
# mismo handle se añade el número de artículo como sufijo.
HANDLE_PATRON = "{estilo}-{color}"
HANDLE_MAXIMO = 255
HANDLE_SUFIJO_EN_COLISION = "articulo"   # "articulo" | "contador"

# ---------------------------------------------------------------------------
# 15. VALIDACIONES
# ---------------------------------------------------------------------------
# Nivel de cada comprobación:
#   "error"       el producto NO se exporta
#   "advertencia" se exporta y conviene revisarlo
#   "nota"        se exporta, sólo queda constancia; no requiere acción
#   "ninguno"     no se comprueba
NIVEL_VALIDACION = {
    "sku_vacio": "error",
    "sku_duplicado": "advertencia",
    "titulo_vacio": "error",
    "precio_vacio": "error",
    "precio_invalido": "error",
    "sin_variantes": "error",
    "categoria_vacia": "advertencia",
    "talla_vacia": "advertencia",
    "sin_imagen": "advertencia",
    "url_invalida": "advertencia",
    # Si el producto SÍ tiene imágenes buenas y sólo algunas salieron mal, no
    # es un problema: se cargan las buenas y se deja constancia de las otras.
    "url_invalida_parcial": "nota",
    "sin_color": "advertencia",
    "sin_marca": "advertencia",
    # El concentrado nunca trae inventario: es una condición global del
    # archivo, no un problema de cada producto. Se informa una sola vez en
    # el Resumen del reporte. Ponlo en "advertencia" si quieres verlo
    # producto por producto.
    "sin_inventario": "ninguno",
    "sin_descripcion": "advertencia",
    # El proveedor no siempre marca la aprobación, y aun así el producto se
    # sube. Queda como nota para saber cuáles no venían aprobadas.
    "no_aprobado": "nota",
    "handle_duplicado": "advertencia",
    "variante_duplicada": "advertencia",
    "ean_duplicado": "advertencia",
    "variantes_huerfanas": "advertencia",
}

# Shopify no admite más de 100 variantes por producto.
MAXIMO_VARIANTES_POR_PRODUCTO = 100

# ---------------------------------------------------------------------------
# 15. LIMPIEZA DE TAGS
# ---------------------------------------------------------------------------
# Las supercategorías de Hybris vienen como rutas: "Accesorios_Caballero_Cinturones".
# Si se convierten tal cual salen tags como "Caballero Cinturones", que repiten
# información que ya está en otro tag y ensucian los filtros de la tienda.
#
# Estos segmentos son ESTRUCTURALES (familia, género, marca): se quitan del
# principio y del final de la ruta, y lo que queda es la categoría real.
#   Accesorios_Caballero_Cinturones -> Cinturones
#   New_Arrivals_Dama               -> New Arrivals
#   Quirelli_Caballero              -> Quirelli  (ya está como marca; se deduplica)
#   Accesorios_Caballero            -> (vacío, se descarta)
TAGS_SEGMENTOS_ESTRUCTURALES = {
    "dama", "caballero", "ninos", "niños", "nino", "niño",
    "hombre", "mujer", "unisex",
    "accesorios", "calzado",
}

# Las marcas se tratan aparte: se quitan del final de la ruta, pero al inicio
# sólo se descartan si NO queda categoría después. Así "Quirelli_Caballero" se
# descarta (la marca ya es su propio tag) y "Flexi_Country_Caballero" conserva
# "Flexi Country", que sí es una línea real de la tienda.
TAGS_SEGMENTOS_MARCA = {"flexi", "quirelli"}

# Unifica singular/plural y acentos: "Cafe"/"Café" y "Plantilla"/"Plantillas"
# dejan de ser dos tags distintos. Gana la forma que aparece primero.
TAGS_UNIFICAR_SINGULAR_PLURAL = True

# Pares que el catálogo escribe de dos formas distintas. La llave se compara
# sin acentos y en minúsculas; el valor es el tag que queda.
TAGS_CANONICOS = {
    "botas botines": "Botas y Botines",
    "botas y botines": "Botas y Botines",
    "bolsas mochilas": "Bolsas y Mochilas",
    "carteras monederos": "Carteras y Monederos",
    "cuidado limpieza": "Cuidado y Limpieza",
}

# Tope de tags por producto. 0 = sin tope. Shopify admite 250, pero una tienda
# con 30 tags por producto es imposible de filtrar.
TAGS_MAXIMO = 0

# ---------------------------------------------------------------------------
# 16. TOLERANCIA A EXCELS DESORDENADOS
# ---------------------------------------------------------------------------
# Con estas opciones en True, el procesador ya no depende de que el archivo
# venga exactamente como el concentrado de Flexi. Los valores fijos de las
# secciones 2 y 3 se siguen intentando PRIMERO; la detección automática es el
# plan B, así que el comportamiento con el archivo actual no cambia.

# Si HOJA_MAESTRO no existe, buscar la hoja que más columnas obligatorias tenga.
DETECTAR_HOJAS_AUTOMATICAMENTE = True

# El encabezado no siempre está en la primera fila: hay archivos con el logo,
# el título del reporte o filas en blanco arriba. Cuántas filas mirar.
DETECTAR_FILA_ENCABEZADO = True
MAXIMO_FILAS_BUSCAR_ENCABEZADO = 15

# Cuántas columnas obligatorias debe reconocer una hoja para considerarla
# candidata a maestro o a variantes.
MINIMO_COLUMNAS_PARA_CANDIDATA = 2

# En vez de saltar un número fijo de filas de metadatos, descartar las filas
# de arriba que no parezcan producto (sin número de artículo utilizable).
# "auto" usa la detección; un número entero conserva el comportamiento viejo.
MAESTRO_FILAS_METADATOS_MODO = "auto"

# Las columnas sin encabezado se identifican por su CONTENIDO, no por su
# posición: si la mayoría de sus valores son URLs, es la de fotografías.
DETECTAR_COLUMNAS_SIN_NOMBRE_POR_CONTENIDO = True


# ---------------------------------------------------------------------------
# 8.1 VOCABULARIO CERRADO Y EJES DEL CALZADO
# ---------------------------------------------------------------------------
# Sale de auditar el catálogo real de la tienda (1,842 productos): 1,240 tags
# distintos, de los cuales ~950 eran códigos de artículo, nombres de modelo y
# marcas de captura. Un tag que aplica a cuatro productos de mil no agrupa
# nada: es ruido en el filtro lateral.
#
# La regla: si un tag no está en este vocabulario, NO se escribe. Se reporta.
TAGS_SOLO_VOCABULARIO = True

# Un producto de calzado responde a cuatro preguntas independientes, y meter
# las cuatro en una sola clase fue lo que produjo 396 productos con dos
# "categorías" a la vez. Un botín de tacón es las tres cosas y ninguna
# contradice a la otra.
#
#   SILUETA  qué forma tiene      -> Botas y Botines, Tenis, Sandalias...
#   CORTE    qué tan alto sube    -> Choclo
#   ALTURA   si lleva tacón       -> Tacón
#   CIERRE   cómo se ajusta       -> Velcro, Agujetas, Slip On, Hebilla, Pulsera
TAGS_EJES_CALZADO = ("silueta", "corte", "altura", "cierre")

# clase -> {tag canónico: (alias en minúscula y sin acentos, ...)}
TAGS_VOCABULARIO = {
    "marca": {
        "Flexi": (), "Quirelli": ("quirelli caballero",), "Coqueta": (), "Audaz": (), "Procliff": (),
        "SCHU": (), "Flexi Country": ("country",), "Flexi Pro": ("pro",),
        # Tecnología, línea blanca y hogar. Van con la grafía de la marca, y
        # el Vendor del producto se normaliza a la misma.
        "Apple": (), "Samsung": (), "Hisense": (), "LG": (), "Motorola": (),
        "Honor": (), "Lenovo": (), "HP": (), "TCL": (), "Daewoo": (), "Epson": (),
        "Nintendo": (), "PlayStation": ("play station",), "Wowdefu": (),
        "Whirlpool": (), "Midea": (), "Mirage": (), "Spring Air": (),
        "Goodyear": (), "Benelli": (),
    },
    "genero": {
        "Dama": ("mujer", "femenino"), "Caballero": ("hombre", "masculino"),
        "Niña": ("nina",), "Niño": ("nino",), "Unisex": (),
    },
    "etapa": {
        "Primeros Pasos": ("bebe",), "Infantil": (),
        "Escolar": ("colegial", "colegio"),
    },
    "tipo": {
        "Calzado": (), "Accesorios": ("accesorios dama", "accesorios caballero"),
        "Ropa": ("playera", "blusa"), "Electrónica": ("electronica", "electronicos"),
        "Electrodomésticos": ("electrodomesticos",), "Hogar": (), "Papelería": ("papeleria",),
        "Automotriz": (), "Tarjeta de Regalo": ("tarjeta de regalo",),
    },
    "silueta": {
        "Botas y Botines": ("botin", "botines", "bota", "botas", "botita", "chelsea", "western", "botas country"),
        "Tenis": ("sneaker", "sneakers"),
        "Sandalias": ("sandalia", "abierta", "semiabierta"),
        "Mocasines": ("mocasin",),
        "Flats y Balerinas": ("balerina", "balerinas", "mary jane", "flat", "flats"),
        # Genérica a propósito: un Oxford o un Derby es un zapato. Se usa
        # cuando el origen no dice una forma más específica.
        "Zapatos": ("zapato", "oxford", "derby"),
        # accesorios
        "Cinturones": ("cinturon",),
        "Carteras y Monederos": ("cartera", "carteras", "monedero"),
        "Bolsas y Mochilas": ("bolsa", "bolsas", "mochila", "mochilas", "tote",
                              "crossbody", "bolsas y carteras", "cartuchera", "lonchera"),
        "Calcetines": ("calcetin", "calcetines", "invisible", "largo"),
        "Gorras": ("gorra", "gorras new era"),
        "Billeteras y Tarjeteros": ("billetera", "tarjetero", "porta pasaporte"),
        "Agujetas": ("agujeta",),
        "Plantillas": ("plantilla", "talonera"),
        "Cuidado del Calzado": ("limpieza", "cuidado", "limpieza y complementos del calzado",
                                "accesorios calzado", "crema", "esponja", "cepillo", "calzador"),
        "Coleccionables": ("coleccionable",),
    },
    # Lo que no es calzado ni accesorio también se agrupa: son las
    # subcolecciones de Ropa, Electrónica, Electrodomésticos y Hogar.
    "categoria": {
        "Playeras y Blusas": (), "Shorts y Pantalones": ("jeans y pantalones", "short", "shorts"),
        "Chamarras": ("chamarra",), "Vestidos": ("vestido",), "Conjuntos": ("conjunto",),
        "Overoles": ("overol",), "Trajes de Baño": ("traje de bano", "trajes de bano"),
        "Pantallas y TV": ("pantallas", "television", "televisiones"), "Celulares": ("celular", "smartphone"),
        "Audio": ("bocina", "bocinas"), "Cómputo": ("computo", "laptop", "laptops y tablets"),
        "Impresión": ("impresion", "impresora"), "Relojes y Wearables": ("smartwatch",),
        "Consolas y Videojuegos": ("consola", "consolas", "videojuegos"),
        "Refrigeración": ("refrigeracion", "refrigerador", "refrigeradores"),
        "Lavado": ("lavadora", "lavadoras", "lavado y secado", "secadora de gas"),
        "Estufas y Microondas": ("estufa", "estufas", "microondas", "estufas y hornos", "horno", "campanas"),
        "Cocina Pequeña": ("cocina pequena", "licuadoras", "batidoras", "batidoas", "procesadores"),
        "Climatización": ("climatizacion", "minisplit"),
        "Batería de Cocina": ("bateria de cocina",), "Descanso": ("colchon",),
        "Llantas": ("llanta",), "Motos y Bicicletas": ("motocicleta", "bicicleta"),
    },
    "corte":  {"Choclo": ("choclos",)},
    "altura": {"Tacón": ("tacon", "tacones", "zapatilla", "zapatillas", "cuna")},
    "cierre": {"Slip On": ("slip on",), "Velcro": ("tira de contacto",),
               "Agujetas": (), "Hebilla": (), "Pulsera": ()},
    "uso": {
        "Casual": (), "De Vestir": ("vestir", "formal", "dress", "semivestir", "ceremonia",
                                    "zapato de vestir", "caballero vestir"),
        "Confort": (), "Deportivo": (), "Outdoor": (), "Urbano": (),
        "Servicio Clínico": ("clinico",), "Seguridad Industrial": ("seguridad", "industrial"),
        "Universitario": (),
    },
    "material": {"Piel": (), "Tejido": (), "Textil": ("algodon",)},
    # "OI-2023" y "PV-2022" son la misma temporada escrita de otra forma.
    "temporada": {f"{t}{a}": (f"{t.lower()}-20{a}",) for t in ("PV", "OI") for a in range(15, 27)},
    "estado": {"Vigente": (), "Outlet": (),
               "Descontinuado": ("nocontinuapv26", "nocontinua")},
    "campana": {"Hot Sale": ("hot sale 2025", "hot sale 3x2", "prehotsale"),
                "Regreso a Clases": ("back to school",),
                "Productos Exclusivos": ("exclusivo", "exclusivos")},
    "color": {c: () for c in (
        "Negro","Café","Tan","Blanco","Gris","Marino","Chocolate","Taupe","Vino","Beige",
        "Multicolor","Nude","Azul","Cognac","Incoloro","Nogal","Rojo","Rosa","Arena",
        "Brandy","Verde Olivo","Marrón","Crema","Moka","Capuccino","Oporto")},
}
# Alias de color que vienen en inglés o mal codificados.
TAGS_VOCABULARIO["color"]["Café"] = ("cafe", "marron", "brown")
TAGS_VOCABULARIO["color"]["Negro"] = ("black",)
TAGS_VOCABULARIO["color"]["Verde Olivo"] = ("olivo",)

# Orden en el que se escriben los tags del producto.
TAGS_ORDEN_CLASES = ("marca", "genero", "etapa", "tipo", "silueta", "categoria", "corte",
                     "altura", "cierre", "uso", "material", "temporada",
                     "estado", "campana", "color")

# Qué se tira, y con qué motivo. El motivo se reporta: sirve para pedirle al
# proveedor que deje de mandarlo.
TAGS_DESCARTES = (
    (r"^\d[\d\-\.%]*$",                         "código de artículo"),
    (r"^[a-z0-9]{4,}\-[a-z0-9]+$",              "código de artículo"),
    (r"^(cps|cu)_",                             "código interno de Hybris"),
    (r"^(captura|segunda carga|carga |noviembre$)", "marca de captura o lote"),
    (r"^desc",                                  "nota interna"),
)
# Tecnologías del fabricante: describen el producto pero no agrupan a nadie.
# Su lugar es la ficha técnica del body, no el filtro de la tienda.
TAGS_TECNOLOGIAS = {
    "inyeccion directa", "inyeccion", "arco", "puntal", "soft", "walking", "gel",
    "softie", "shieldtech", "suela", "sistema", "aire", "velcro", "pie", "hexafoam",
    "recovery", "form", "agarre", "interno", "fusionstep", "antirraspaduras",
}
# Atributos que no agrupan: describen una variante, no una categoría.
TAGS_ATRIBUTOS = {"cerrado", "cerrada", "abierto", "vista", "estampados", "color"}

# Cuando el tag y el título se contradicen, gana el título: es lo que el
# cliente lee y lo que el vendedor escribió a conciencia.
TAGS_SILUETA_EN_TITULO = (
    ("Botas y Botines",   r"^\s*(bota|botita|botin)"),
    ("Tenis",             r"^\s*(tenis|sneaker)"),
    ("Sandalias",         r"^\s*(sandalia|huarache)"),
    ("Flats y Balerinas", r"^\s*(balerina|flat)"),
    ("Mocasines",         r"^\s*(mocasin|derby|oxford)"),
    ("Zapatos",           r"^\s*zapato"),
)
TAGS_CIERRE_EN_TITULO = (
    ("Slip On",  r"slip ?on"),
    ("Velcro",   r"tira de contacto|velcro"),
    ("Agujetas", r"agujeta"),
    ("Hebilla",  r"hebilla"),
    ("Pulsera",  r"pulsera"),
)
# Los accesorios casi nunca traen su categoría en los tags: se lee del título.
TAGS_ACCESORIO_EN_TITULO = (
    ("Cuidado del Calzado", r"crema|esponja|cepillo|calzador|grasa|cera|toallita|"
                            r"espuma|renovador|desodorante|dilatador|spray|kit de limpieza|"
                            r"repelente|impermeabilizante|brillo|abrillantadora"),
    ("Plantillas",          r"plantilla|talonera|talonerita|almohadilla|pads|protector(es)? tac"),
    ("Agujetas",            r"agujeta"),
    ("Gorras",              r"gorra"),
    ("Cinturones",          r"cintur[oó]n"),
    ("Bolsas y Mochilas",   r"mochila|bolsa|cartuchera|lonchera|tote"),
    ("Billeteras y Tarjeteros", r"billetera|tarjetero|porta pasaporte"),
    ("Carteras y Monederos",    r"cartera|monedero"),
    ("Calcetines",          r"calcet[ií]n|calceta"),
)

TAGS_GENERO_EN_TITULO = (
    ("Caballero", r"para hombre|caballero"),
    ("Dama",      r"para mujer|dama"),
    ("Niña",      r"para nina"),
    ("Niño",      r"para nino"),
)

# En electrónica también manda el título: un iPhone cuya ficha dice "Pantalla
# de 6.3 pulgadas" es un celular, y una Galaxy Tab es cómputo. El ORDEN importa:
# gana el primero que coincida, por eso reloj y tablet van antes que celular,
# y celular antes que pantalla.
TAGS_CATEGORIA_EN_TITULO = (
    ("Relojes y Wearables",    r"\bwatch\b|smartwatch|\breloj"),
    ("Cómputo",                r"\btab\b|tablet|ipad|laptop|macbook"),
    ("Celulares",              r"iphone|galaxy a\d|\bmoto\b|motorola|\bhonor\b|smart ?phone|celular"),
    ("Consolas y Videojuegos", r"consola|nintendo|xbox|playstation|play station"),
    ("Pantallas y TV",         r"smart tv|pantalla|television|\btv\b"),
    ("Audio",                  r"bocina|soundbar|audifono"),
    ("Impresión",              r"multifuncional|impresora"),
)

# "Zapatilla" es tacón en dama, pero en la línea infantil (Coqueta) es el zapato
# de vestir plano: así se colaron 16 balerinas de niña en "Niña · Tacón". En
# Niña/Niño el tacón sólo se acepta si el título lo dice con esa palabra.
TAGS_TACON_INFANTIL_SOLO_EN_TITULO = True
TAGS_TACON_EN_TITULO = r"\btacon"

# Una categoría de accesorio sólo aplica si el producto ES un accesorio. Un
# zapato "con Plantilla Hexafoam" no va en la colección Plantillas: así se
# colaron 29 zapatos Quirelli ahí.
TAGS_ACCESORIO_SOLO_EN_ACCESORIOS = True

# Si tras aplicar todo quedan dos siluetas y el título no desempata, el
# producto NO se adivina: se manda a revisión, como las tres detenciones del
# ETS para los mapeos de CT.
TAGS_DETENER_SI_HAY_CONFLICTO = True

# Un accesorio sin género es unisex; dejarlo en blanco lo saca de los filtros.
TAGS_ACCESORIO_SIN_GENERO_ES_UNISEX = True
# Un calzado sin silueta es un zapato: para eso existe la silueta genérica.
TAGS_CALZADO_SIN_SILUETA = "Zapatos"

# ---------------------------------------------------------------------------
# 8.2 FILTROS DE LA TIENDA (metafields)
# ---------------------------------------------------------------------------
# Los tags deciden a qué colección entra un producto; los filtros de la
# tienda salen de metafields, uno por pregunta del cliente. Así el filtro
# lateral muestra "Categoría: Tenis, Botas…" en su propio bloque, en vez de
# una sola lista revuelta con colores, temporadas y marcas.
#
# clave del metafield (namespace custom) -> (nombre visible, clases que lo llenan)
METAFIELDS_FILTRO = {
    "genero":    ("Género",    ("genero",)),
    "etapa":     ("Etapa",     ("etapa",)),
    "categoria": ("Categoría", ("silueta", "categoria")),
    "ocasion":   ("Ocasión",   ("uso",)),
    "cierre":    ("Cierre",    ("cierre",)),
    "altura":    ("Tacón",     ("altura",)),
    "corte":     ("Corte",     ("corte",)),
    "material":  ("Material",  ("material",)),
}

# Las mismas columnas van en el CSV del Excel, para que los filtros entren en
# la misma importación y no haga falta un segundo paso después.
# Formato de Shopify: "Nombre (product.metafields.custom.clave)" y, en las
# listas, los valores separados por "; ". Las definiciones ya existen en la
# tienda con valores cerrados: un valor fuera de la lista hace fallar la fila.
METAFIELDS_EN_CSV = True
METAFIELDS_NAMESPACE = "custom"
METAFIELDS_SEPARADOR_CSV = "; "
