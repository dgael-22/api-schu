# Enriquecedor de catálogo

Completa los artículos que el concentrado dejó incompletos, con lo que la propia
marca publica en su sitio. Es un paso **opcional** y aparte: el procesador sigue
funcionando sin él y sin sus dependencias.

---

## Las tres reglas

1. **Sólo se llena lo que está vacío.** Nunca se pisa un dato del proveedor,
   aunque el de la marca "se vea mejor". Si los dos existen y difieren, se anota
   en la hoja *Discrepancias* para que una persona lo revise.
2. **Nada se inventa.** Si la marca no publica ese artículo, se reporta como no
   encontrado y ya. No se trae un producto "parecido".
3. **Nada se publica solo.** Todo lo enriquecido sale como `draft`, con la URL
   de donde salió cada dato y la fecha de consulta.

---

## Cómo se usa

```powershell
pip install -r requirements-enriquecer.txt
python -m playwright install chromium

python main.py                          # primero el proceso normal
python enriquecer.py --limite 5         # prueba con 5 artículos
python enriquecer.py                    # ya en serio
```

Sale `output\enriquecido.xlsx` con tres hojas: **Encontrados** (con las URLs de
las imágenes), **No encontrados** (con el motivo) y **Discrepancias**.

Opciones útiles: `--marca`, `--faltantes` (otro archivo de entrada),
`--reconstruir-indice`, `--ver-navegador` (abre Chrome a la vista para depurar).

---

## Cómo está armado

```
enriquecedor/
  modelo.py            Solicitud (lo que falta) y Ficha (lo que se encontró)
  base.py              FuenteMarca: el contrato que cumple cada marca
  motor.py             orquesta; aquí vive la regla de no pisar datos
  fuentes/
    __init__.py        REGISTRO de marcas — aquí se da de alta una nueva
    flexi.py           driver de flexi.com.mx (Playwright)
    flexi_parseo.py    parseo del HTML, sin navegador y con pruebas
enriquecer.py          CLI
tests/                 26 pruebas, ninguna toca la red
```

El parseo está separado del navegador a propósito: se prueba con HTML guardado,
sin red y sin Playwright. Los fixtures de `tests/fixture_flexi.py` son recortes
**reales** del sitio, capturados el 7-sep-2026.

---

## Lo que se descubrió del sitio de Flexi

Esto es lo que hace posible el cruce, y lo único que hay que revisar si algún
día deja de funcionar:

| Cosa | Forma |
|---|---|
| URL de producto | `/es/producto/<EAN>-<slug>` — el EAN va en la propia URL |
| Fin del slug | `...-estilo-<estilo>-<color>` |
| Ficha | trae JSON-LD `schema.org/Product` con `sku` (el EAN), `name` y `offers` |
| Referencia cruzada | la ficha muestra `ID <EAN> - <número SAP>` |
| Imágenes | `apiecom.flexi.com.mx/medias/<estilo>-<color>-<vista>.jpg?context=<token>` |

Esa línea `ID <EAN> - <SAP>` es el puente con el concentrado: el número SAP es
exactamente el `Número de artículo` del maestro.

**El token `?context=` no se puede inventar.** Va firmado, así que la URL de la
imagen hay que leerla de la página tal cual; recortarla la rompe.

El sitio es una SPA de SAP Commerce (Spartacus): el HTML por HTTP viene vacío.
Por eso Playwright, y por eso el enriquecedor trabaja en dos tiempos — primero
construye un índice recorriendo las categorías públicas (se guarda en
`output/indice_flexi.json` para no volver a barrer), y sólo después abre la
ficha de los artículos que interesan.

---

## Cómo agregar otra marca (Onena, Quirelli, la que sea)

1. **Mira el sitio primero.** Necesitas saber tres cosas: cómo se ve la URL de
   un producto, si el catálogo se pinta con JavaScript o viene en el HTML, y si
   hay algún identificador que se pueda cruzar con tu Excel (EAN, SKU, estilo).
   Sin ese identificador común no hay enriquecimiento posible, sólo adivinanza.
2. **Copia `flexi_parseo.py` a `<marca>_parseo.py`** y ajusta las expresiones a
   las formas de ESE sitio. Escribe sus pruebas con HTML real, no inventado.
3. **Copia `flexi.py` a `<marca>.py`** y ajusta `BASE` y `CATEGORIAS`. Si el
   sitio NO es una SPA, ni siquiera necesitas Playwright: basta con bajar el
   HTML y parsearlo, y la fuente queda mucho más simple y rápida.
4. **Regístrala** en `fuentes/__init__.py`, en el diccionario `FUENTES`.

El motor, el CLI y el reporte no se tocan.

---

## Antes de usar las imágenes de la marca

Confirma por escrito que SCHU tiene permiso de usar las fotos y descripciones
del proveedor en su tienda. Siendo distribuidor lo normal es que sí, pero
conviene tenerlo por escrito antes de publicar cientos de imágenes ajenas.
