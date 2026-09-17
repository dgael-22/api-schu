# Guía del catálogo SCHU

Todo el proyecto vive en **`C:\Users\Usuario\trabajo\schu-catalogo`**.
Una sola carpeta, un solo servidor, una sola terminal.

---

## 1. Instalación (una vez)

```powershell
cd $HOME\trabajo\schu-catalogo
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-enriquecer.txt
python -m playwright install chromium
```

El venv **tiene que crearse aquí**: guarda rutas absolutas, así que copiar uno de
otra carpeta lo rompe. Los navegadores de Playwright se comparten en
`%LOCALAPPDATA%\ms-playwright`, así que si ya los bajaste no se vuelven a bajar.

De ahí en adelante, cada vez que abras una terminal nueva:

```powershell
cd $HOME\trabajo\schu-catalogo
.\venv\Scripts\Activate.ps1
```

Sabes que estás bien si el prompt empieza con `(venv)`.
Si PowerShell bloquea el activate: `Set-ExecutionPolicy -Scope Process RemoteSigned`.

En VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.\venv\Scripts\python.exe`,
y ya no tienes que activar nada nunca más.

---

## 2. Todo desde el servidor (una terminal)

```powershell
python servidor.py
```

Abre `http://127.0.0.1:8000`. Ahí subes el Excel del proveedor y descargas el
resultado. En `http://127.0.0.1:8000/docs` están todos los endpoints y se pueden
probar desde el navegador.

El flujo completo, incluido el enriquecimiento, ya vive en ese mismo servidor:

| Paso | Endpoint |
|---|---|
| Subir el Excel | `POST /api/procesar` → devuelve `202` con un `id` |
| Ver el avance | `GET /api/trabajos/{id}` hasta que diga `terminado` |
| Descargar | `GET /api/trabajos/{id}/descargar/excel` · `/csv` · `/reporte` · `/zip` |
| **Enriquecer** artículos incompletos | `POST /api/trabajos/{id}/enriquecer?limite=5` → `202` |
| Descargar lo enriquecido | `GET /api/trabajos/{id}/descargar/enriquecido` |
| **Buscar imágenes** que faltan | `POST /api/trabajos/{id}/enriquecer-imagenes?minimo=3&limite=5` → `202` |
| Descargar el reporte de imágenes | `GET /api/trabajos/{id}/descargar/imagenes` |
| Descargar el CSV para importar | `GET /api/trabajos/{id}/descargar/imagenes_csv` |
| Marcas soportadas | `GET /api/enriquecer/marcas` |
| Vocabulario de tags y filtros | `GET /api/vocabulario` |
| **Reclasificar** un export de Shopify | `POST /api/retaguear` → CSV por handle (tags, Vendor, Type, filtros) |
| Salud y configuración | `GET /api/salud` · `GET /api/configuracion` |

Enriquecer sólo funciona sobre un trabajo ya `terminado`, porque parte del
reporte que generó el procesamiento. Corre en segundo plano —abre un navegador
y tarda minutos—, así que el servidor te contesta de inmediato con `202` y tú
consultas el estado. **La primera vez usa `?limite=5`.**

Detener el servidor: `Ctrl + C`.

---

## 3. Lo mismo por línea de comandos

Si prefieres no levantar el servidor:

```powershell
python main.py                    # procesa input\ y escribe output\
python verificar.py               # 23 comprobaciones del resultado
python enriquecer.py --limite 5   # completa los artículos incompletos
python enriquecer.py --imagenes --minimo-imagenes 3 --limite 5
python retaguear.py export.csv     # escribe output\organizacion.csv
python -m unittest discover -s tests   # 53 pruebas, ninguna toca la red
```

`retaguear.py` pasa un export de Shopify por el vocabulario cerrado
(`config/rules.py`, secciones 8.1 y 8.2). Su salida NO se importa en Shopify.

Las dos vías llaman al mismo código: `processors/pipeline.py` para procesar y
`enriquecedor/tarea.py` para enriquecer. No hay dos versiones de nada.

Opciones útiles de `main.py`: `--origen otro.xlsx`, `--validar-imagenes`, `--verboso`.
De `enriquecer.py`: `--marca`, `--faltantes`, `--reconstruir-indice`, `--ver-navegador`.

---

## 4. Qué hace cada cosa

**El procesador** convierte el Excel del proveedor en el formato exacto que
Shopify importa. Detecta las columnas por alias, aguanta hojas renombradas,
encabezados que no están en la primera fila y columnas sin nombre. Nunca inventa
un dato: si no viene en el origen, queda vacío y aparece en el reporte.

**El enriquecedor** completa los artículos incompletos con lo que la propia marca
publica en su sitio. Tres reglas: sólo llena lo que está vacío, nunca inventa, y
lo que completa sale como borrador con la URL de donde salió y la fecha.

---

## 5. Errores que vas a ver

**`ModuleNotFoundError: No module named 'pandas'`** — estás en el Python
equivocado. Activa el venv de esta carpeta.

**`PermissionError` al final del proceso** — tienes
`products_export_limpio.xlsx` abierto en Excel. Ciérralo y vuelve a correr.

**`Falta Playwright`** — lo instalaste en el Python global, no en el venv.
Actívalo y repite el `pip install -r requirements-enriquecer.txt`.

**Los 31 huérfanos siempre salen en "No encontrados"** — no es una falla. Esos
artículos tampoco están publicados en el sitio de Flexi; se comprobó por código
SAP y por EAN. Se resuelven pidiéndole las fichas al proveedor.

---

## 6. Estructura

```
schu-catalogo\
  main.py              procesar por línea de comandos
  servidor.py          levantar la API
  enriquecer.py        enriquecer por línea de comandos
  retaguear.py         reclasificar un export de Shopify con el vocabulario
  verificar.py         23 comprobaciones
  config\rules.py      TODAS las reglas de negocio
  processors\          lectura, limpieza, normalización, exportación
  enriquecedor\        motor + fuentes por marca
  api\                 FastAPI: app.py, trabajos.py, rutas_enriquecer.py
  tests\               53 pruebas, ninguna toca la red
  input\  output\      entrada y salida
  ENRIQUECEDOR.md      el enriquecedor a detalle y cómo agregar una marca
```

---

## 7. Pendientes

- Cargar el inventario en Shopify: el concentrado no trae existencias, así que
  todo sale en 0 con política `deny` y no se vende hasta cargarlo.
- Pedirle al proveedor las fichas de los 31 artículos huérfanos.
- Revisar los 15 productos con colisión de handle antes de importar.
- Confirmar por escrito que SCHU puede usar las fotos y descripciones del
  proveedor en la tienda.
- La API **no tiene autenticación**. Sirve en `127.0.0.1` y así está bien;
  antes de exponerla con `--publico` o fuera de la red interna necesita token
  y HTTPS.

---

## 8. Niveles del reporte

| Nivel | Qué significa |
|---|---|
| **ERROR** | el producto NO se exporta |
| **ADVERTENCIA** | se exporta, pero conviene revisarlo |
| **NOTA** | se exporta y queda constancia; no requiere acción |

Dos cosas bajaron a **nota** el 7 de septiembre, porque no son problemas:

- **`no_aprobado`** — "Se agregó el producto, pero el proveedor no lo marcó como
  aprobado". Son 100 productos. Se suben igual; sólo queda el registro de
  cuáles no venían aprobados.
- **`url_invalida_parcial`** — cuando un producto tiene fotos buenas y alguna
  mala. **Basta con que quede una imagen buena para publicarlo con ella**; las
  URL rotas se descartan y se anota cuántas fueron. Sólo cuando NO queda
  ninguna imagen se marca `sin_imagen` como advertencia.

Efecto en el resumen: los productos "sin ninguna observación" pasaron de 766 a
**861**, y las advertencias de 180 a **85**. Los 946 se siguen exportando.

---

## 9. Traer las imágenes desde el sitio de la marca

Para los productos que salieron con pocas fotos o ninguna:

```powershell
python enriquecer.py --imagenes --minimo-imagenes 3 --limite 5
```

Lee `output\products_export_limpio.csv`, junta los que tienen menos de
`--minimo-imagenes`, y los busca en el sitio de su marca usando el `Variant SKU`
(el número SAP) y el `Variant Barcode` (el EAN) — que son justo los dos
identificadores con los que la marca indexa sus fichas.

Deja dos archivos:

- `output\imagenes_encontradas.xlsx` — qué encontró, qué no y por qué
- `output\imagenes_encontradas_shopify.csv` — `Handle`, `Image Src`,
  `Image Position`, listo para importar en Shopify y agregar sólo las fotos
  sin tocar nada más del producto

**Revísalo antes de importarlo.** Y ojo: hoy sólo Flexi tiene fuente
registrada; los productos Quirelli van a salir como "sin fuente" hasta que
veamos su sitio. Cuando usas `--limite`, el tope se gasta primero en las marcas
que sí tienen adaptador, para que la prueba diga algo útil.

Lo mismo está en la API: `POST /api/trabajos/{id}/enriquecer-imagenes`, con las
descargas `imagenes` (el reporte) e `imagenes_csv` (el listo para importar).
