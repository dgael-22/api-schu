# schu-catalogo

Convierte el concentrado de Excel del proveedor (SAP Hybris de Flexi/Quirelli) en el export exacto de productos de Shopify, y reclasifica exports de la tienda con el vocabulario cerrado. Python · FastAPI. Guía de uso: `GUIA.md`.

**Es el proyecto principal.** `Downloads\excel-shopify-processor` es una copia sincronizada el 15 sep: un cambio de reglas se hace aquí y se copia allá, comprobando que `retaguear.py` dé el mismo CSV en ambos.

## Comandos

```bash
.\venv\Scripts\Activate.ps1
python main.py                          # lee input/, escribe output/
python verificar.py                     # debe salir 23/23 antes de dar por buena una salida
python -m unittest discover -s tests    # 53 pruebas, ninguna toca la red
python servidor.py                      # API en http://127.0.0.1:8000 · /docs
python retaguear.py <export.csv> D:\api-ct\data\organizacion.csv --vocabulario D:\api-ct\data\vocabulario.json
```

`retaguear.py` y `POST /api/retaguear` devuelven, por handle, tags, Vendor, Type y los metafields de los filtros. **No es un CSV para importar**: lo aplica `D:\api-ct` con `npm run shopify:organizar`. `GET /api/vocabulario` da las listas en JSON.

## Reglas del proyecto

- **Toda regla de negocio vive en `config/rules.py`**, no en el procesador.
- **Código y comentarios en español.**
- **No inventar datos.** Si el origen no lo dice, el campo queda vacío y se reporta. `Product Category` va vacía a propósito.
- Respaldo en `_respaldo/` antes de tocar un procesador.

## Vocabulario cerrado de tags (8.1 de rules.py)

**Un tag que no está en el vocabulario no se escribe: se reporta.** En la tienda había 1,240 tags distintos y ~950 eran códigos y nombres de modelo. `TAGS_INCLUIR_ESTILO = False` por lo mismo.

Los cuatro ejes del calzado van en clases separadas (juntarlos dio 396 productos con dos "categorías"):

| Eje | Responde | Ejemplos |
|---|---|---|
| Silueta | qué forma tiene | Botas y Botines, Tenis, Sandalias, Mocasines, Flats y Balerinas, Zapatos |
| Corte | qué tan alto sube | Choclo |
| Altura | si lleva tacón | Tacón |
| Cierre | cómo se ajusta | Velcro, Agujetas, Slip On, Hebilla, Pulsera |

Los filtros de la tienda (metafields `custom.*`) salen de estas clases: sección 8.2. **El CSV del Excel ya los trae** en 8 columnas al final (`Nombre (product.metafields.custom.clave)`, listas con `; `), así entran en la misma importación.

### Reglas que resuelven ambigüedad

- **El título manda sobre el tag.** `Zapato` pierde contra cualquier silueta específica.
- **Una categoría de accesorio sólo aplica a un accesorio**: ni un zapato "con plantilla" va en Plantillas ni una prenda "con cinturón" en Cinturones.
- En electrónica manda el título (`TAGS_CATEGORIA_EN_TITULO`): un iPhone cuya ficha dice "Pantalla" es un celular.
- **"Zapatilla" es tacón en dama, no en niña ni niño**: ahí sólo cuenta si el título dice "tacón".
- Accesorio sin género → `Unisex`; calzado sin silueta → `Zapatos`.
- Dos siluetas sin desempate → **a revisión, no se adivina** (`TAGS_DETENER_SI_HAY_CONFLICTO`).

Nunca son tag: códigos de artículo · nombres de modelo · marcas de captura (`CAPTURA17AGOSTO2026`) · tecnologías del fabricante (van en la ficha).

## Estructura

```
config/rules.py          todas las reglas de negocio
processors/              excel_reader · cleaner · normalizer · products · images · validator · exporter
  vocabulario.py         clasifica tags y resuelve conflictos
  retaguear.py           export de Shopify -> tags, Vendor, Type y filtros
  pipeline.py            procesar_catalogo(), la usan main.py y la API
enriquecedor/            completa fichas desde el sitio de la marca (ENRIQUECEDOR.md)
api/                     FastAPI: app.py, trabajos.py, rutas_enriquecer.py
```

## Pendiente con el proveedor

31 artículos con EAN y precio sin ficha · 15 colisiones de handle · mojibake en `CAFÉ` · 72 sin color · `Corrida MEX` inconsistente.

## Cuidado con Shopify

- **Distingue mayúsculas en los tags.** Una colección que busca `Calzado` no encuentra `CALZADO`, sin aviso.
- **Nunca un CSV parcial.** Sólo Handle y Tags le hace creer a Shopify que el producto perdió sus variantes.
- **Importar con handles distintos duplica productos** (pasó el 4 y el 14 sep): comparar handles contra la tienda antes.
