# Análisis de los archivos y tabla de mapeo

Documento de referencia del análisis hecho antes de programar. Si llega un
concentrado nuevo, este es el punto de partida para revisar si las reglas
siguen sirviendo.

---

## 1. `concentrado fp(2).xlsx`

Es un export de SAP Hybris. Tiene 7 hojas pero sólo 3 contienen datos.

| Hoja | Filas útiles | Qué es |
|---|---|---|
| `TypeTemplate` | — | plantilla vacía del export. Se ignora |
| `TypeSystem` | — | definición de tipos de Hybris. Se ignora |
| `ClassificationTypeSystem` | — | definición de clasificaciones. Se ignora |
| `HeaderPrompt` | — | ayuda de encabezados. Se ignora |
| `FlexiVariantProductColor` | **946** | maestro producto-color |
| `CALZADO EANS Y PRECIOS` | 7,641 | talla + EAN + precio de calzado |
| `ACCESORIOS EANS Y PRECIOS` | 565 | talla + EAN + precio de accesorios |

### `FlexiVariantProductColor`

Las **2 primeras filas bajo el encabezado son metadatos**, no productos: una
trae los `ReferenceFormat` de Hybris y otra la etiqueta "Links Fotografías".
Se saltan (`MAESTRO_FILAS_METADATOS = 2`).

Las 2 últimas columnas vienen **sin encabezado** en el archivo; por posición
son "Links Fotografías" y "Familia" (`MAESTRO_COLUMNAS_SIN_NOMBRE`).

Llenado de las 28 columnas:

| Columna | Llenas | Únicos |
|---|---|---|
| `Número de artículo*^` | 100 % | 946 (sin duplicados) |
| `Identificador[es]` | 100 % | 942 |
| `Descripción[es]` | 100 % | 898 |
| `Supercategorías+` | 100 % | 452 |
| `Producto base*` | 100 % | 600 |
| `Links Fotografías` | 100 % | 946 |
| `Familia` | 100 % | 2 (CALZADO 649 / ACCESORIOS 297) |
| `Aprobación` | 100 % | approved 846, check 96, unapproved 4 |
| `Nombre de línea[es]` | 99.7 % | 292 |
| `Color SAP[es]` | 92.4 % | 97 |
| `Línea[es]` | 91 % | 182 |
| `Recio Sap` | 89 % | 6 |
| `Construcción SAP` | 88.7 % | 16 |
| `Descripción Limpieza[es]` | 85 % | 64 |
| `Forro[es]` | 70.5 % | 15 |
| `Acabado[es]` | 70 % | 29 |
| `Ancho[es]`, `Construcción[es]`, `Corrida MEX`, `Tipo Piel Sap` | 68.6 % | — |
| `Material para limpieza` | 65 % | 18 |
| `Forro Sap` | 51 % | 6 |
| `Altura Tacón[es]` | 31 % | 50 |
| `Altura Media Plataforma[es]`, `Altura Tubo Bota[es]` | 10.9 % | — |
| `Diámetro Tubo Bota[es]` | 6 % | 13 |

### Hojas de EAN y precio

Ambas tienen las mismas 5 columnas: `Prod.SAP`, `Descripcion Esp`, `Talla`,
`Cod EAN/UPC`, `$ FULL`. **Ninguna celda vacía, ningún EAN repetido, ninguna
combinación artículo+talla repetida, y el precio no varía entre tallas del
mismo artículo.** Es la parte más limpia del archivo.

### El cruce

`Número de artículo*^` (maestro) = `Prod.SAP` (hojas de EAN).

- Los **946** productos del maestro tienen tallas. Ninguno se queda sin.
- **31** códigos SAP aparecen en las hojas de EAN pero **no** en el maestro:
  tienen talla, EAN y precio, pero ni título ni color ni imagen. No se pueden
  exportar; quedan listados en el reporte como `variantes_huerfanas`.

---

## 2. `products_export_1 (1)` — la plantilla

Export real de Shopify: **44 columnas, 8,625 filas, 1,009 productos**. Ya
contiene 310 productos Flexi/Quirelli, y ese precedente resolvió casi todas las
dudas de formato.

### Cómo se estructura un producto

```
Fila 1 del handle : Handle + TODOS los campos del producto + variante 1 + imagen 1
Fila 2..n         : Handle + campos de variante + imagen n
Filas sobrantes   : Handle + Image Src + Image Position   (cuando hay más imágenes que variantes)
```

Los campos del producto (`Title`, `Vendor`, `Type`, `Tags`, `Body (HTML)`,
`Published`, `Status`, `Gift Card`, `Option1 Name`) van **sólo en la primera
fila**. Repetirlos en las demás rompe la importación.

### Qué hacen los productos Flexi/Quirelli que ya están cargados

| Campo | Valor |
|---|---|
| `Handle` | `88602-negro` — estilo + color |
| `Option1 Name` | `Talla`, sin Option2 ni Option3 |
| `Option1 Value` | `25`, `25.5`, `26`… |
| `Variant SKU` | el mismo número SAP para todas las tallas |
| `Variant Grams` | `0.0` · `Variant Weight Unit`: `kg` |
| `Published` / `Status` | `true` / `active` |
| `Variant Inventory Tracker` | `shopify` |

> Los SKU aparecen en el CSV como `'1390014023`. Ese apóstrofo lo añadió Excel
> al abrir el archivo, **no es parte del dato**. En la salida se escriben las
> celdas con formato de texto, que consigue lo mismo sin ensuciar el valor.
> Si alguna vez hace falta reproducir el archivo con apóstrofo, está
> `SKU_PREFIJO_APOSTROFO` en `config/rules.py`.

---

## 3. Tabla de mapeo

| Columna destino (Shopify) | Origen | Transformación |
|---|---|---|
| `Handle` | `Producto base*` + `Color SAP[es]` | `136707:Staged:…` → `136707`; slug ASCII; sufijo con el nº de artículo si choca |
| `Title` | `Identificador[es]` | limpiar espacios y mojibake |
| `Body (HTML)` | `Descripción[es]` + `Descripción Limpieza[es]` | envolver en `<p>` si no trae HTML; la limpieza va en párrafo aparte |
| `Vendor` | detectado en `Identificador[es]`, `Descripción[es]`, `Supercategorías+` | Flexi 755 / Quirelli 191 |
| `Product Category` | — | **sin origen**, queda vacía |
| `Type` | `Familia` + género de `Supercategorías+` | `calzado-dama`, `calzado-caballero`, `calzado-ninos`, `accesorios` |
| `Tags` | `Supercategorías+`, `Nombre de línea[es]`, `Color SAP[es]`, marca, estilo | se descartan `aesth*`, `sales_*`, `stock_*`, `vig`, `fxi`, `CPS_*`, `CU_*` |
| `Published` | fijo | `true` |
| `Option1 Name` | fijo | `Talla` |
| `Option1 Value` | `Talla` (hojas EAN) | `220`→`22`, `225`→`22.5`; cinturones `32-44` y letras sin tocar |
| `Option2/3 *` | — | vacías (con `AGRUPACION="producto_base"`, Option2 = Color) |
| `Variant SKU` | `Prod.SAP` | texto, conserva ceros a la izquierda |
| `Variant Grams` | fijo | `0.0` |
| `Variant Inventory Tracker` | fijo | `shopify` |
| `Variant Inventory Qty` | — | **sin origen**, `0` + aviso |
| `Variant Inventory Policy` | fijo | `deny` |
| `Variant Fulfillment Service` | fijo | `manual` |
| `Variant Price` | `$ FULL` | `1099` → `1099.00`; el valor no cambia |
| `Variant Compare At Price` | — | **sin origen** |
| `Variant Requires Shipping` / `Taxable` | fijo | `true` / `true` |
| `Unit Price *` | — | **sin origen** |
| `Variant Barcode` | `Cod EAN/UPC` | texto |
| `Image Src` | `Links Fotografías` | separar por coma; 2-8 por producto (media 6.7) |
| `Image Position` | calculado | `1, 2, 3…` dentro de cada handle |
| `Image Alt Text` | — | **sin origen**, vacío (no se inventan textos) |
| `Gift Card` | fijo | `false` |
| `SEO Title` / `SEO Description` | — | **sin origen** |
| `Variant Image` | — | **sin origen** |
| `Variant Weight Unit` | fijo | `kg` |
| `Variant Tax Code` / `Cost per item` | — | **sin origen** |
| `Status` | `Aprobación` | `active` (configurable a `draft` para los no aprobados) |

---

## 4. Problemas encontrados en los datos

| # | Problema | Cuántos | Qué se hace |
|---|---|---|---|
| 1 | Mojibake de codificación: `CAF?`, `NEGRO CAF?` | 2 valores | se corrigen a `CAFÉ` |
| 2 | `CAFE` sin acento conviviendo con `CAFÉ` | — | se unifica para el slug, no para el texto visible |
| 3 | Handles que chocan: mismo estilo y color en artículos distintos | 15 | se añade el nº de artículo como sufijo; queda anotado |
| 4 | Productos sin color (calcetines, cremas, agujetas) | 72 | el handle usa sólo el estilo |
| 5 | Productos no aprobados (`check` / `unapproved`) | 100 | se exportan igual, marcados en el reporte |
| 6 | Artículos con EAN sin ficha en el maestro | 31 | no se exportan; listados en el reporte |
| 7 | `Corrida MEX` inconsistente (`25 AL 30`, `25-30 Y 31`, `22 A 27`) | 11 formas | informativo: las tallas reales salen de los EAN |
| 8 | Tallas ambiguas en accesorios | — | sólo se divide entre 10 si son 3 dígitos múltiplos de 5 |
| 9 | Espacios dobles dentro de los títulos | 26 | se colapsan a uno |
| 10 | Sin columna de inventario | todo | se exporta `0` y se avisa |
| 11 | Sin columna de marca | todo | se detecta del texto; nunca se inventa |
| 12 | Títulos duplicados en el maestro | 4 | son productos distintos con el mismo nombre; se conservan los dos |

### El caso de las tallas, en detalle

El concentrado guarda las tallas de calzado en milímetros × 10, pero no todos
los números son tallas de calzado:

| Producto | Talla en el origen | Qué significa | Resultado |
|---|---|---|---|
| Mocasín | `220`, `225` | 22 y 22.5 mexicano | `22`, `22.5` |
| Plantilla de gel | `210` … `310` | 21 a 31 | `21` … `31` |
| Cinturón | `32` … `44` | medida de cinturón | `32` … `44` sin tocar |
| Calcetín, crema | `UNI`, `S`, `M`, `L` | talla única o de letra | literal |

La regla que los separa: **sólo se divide entre 10 un número de 3 dígitos que
sea múltiplo de 5 y esté entre 130 y 450**. Un cinturón del 44 nunca cumple
esas condiciones, así que nunca se convierte en un 4.4.
