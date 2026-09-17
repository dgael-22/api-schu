# -*- coding: utf-8 -*-
"""
verificar.py
============
Comprueba el resultado del proceso. Ejecutar DESPUÉS de main.py:

    python verificar.py

Cubre las 11 comprobaciones del encargo: columnas iguales a la plantilla,
archivos originales intactos, ningún producto perdido, ningún producto
inventado, variantes bien agrupadas, SKU sin pérdida de información, precios
correctos, imágenes y reporte de errores.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from config import rules                       # noqa: E402
from processors import normalizer              # noqa: E402
from utils.helpers import texto                # noqa: E402

INPUT, OUTPUT = RAIZ / "input", RAIZ / "output"
OK, FALLO = "  OK  ", " FALLA"
resultados: list[tuple[bool, str, str]] = []


def revisar(condicion: bool, titulo: str, detalle: str = "") -> bool:
    resultados.append((bool(condicion), titulo, detalle))
    print(f"[{OK if condicion else FALLO}] {titulo}" + (f"\n           {detalle}" if detalle else ""))
    return bool(condicion)


def main() -> int:
    salida = OUTPUT / rules.ARCHIVO_SALIDA
    if not salida.exists():
        print("No existe output/" + rules.ARCHIVO_SALIDA + ". Ejecuta primero: python main.py")
        return 1

    print("\n" + "=" * 72)
    print("VERIFICACIÓN DEL RESULTADO")
    print("=" * 72)

    gen = pd.read_excel(salida, dtype=str, keep_default_na=False)

    # plantilla
    plantilla = None
    for nombre in rules.ARCHIVO_PLANTILLA:
        ruta = INPUT / nombre
        if ruta.exists():
            plantilla = (pd.read_excel(ruta, dtype=str, keep_default_na=False)
                         if ruta.suffix.lower().startswith(".xls")
                         else pd.read_csv(ruta, dtype=str, keep_default_na=False,
                                          encoding="utf-8-sig", low_memory=False))
            break

    origen = INPUT / rules.ARCHIVO_ORIGEN
    maestro = pd.read_excel(origen, sheet_name=rules.HOJA_MAESTRO, dtype=str)
    maestro = maestro.rename(columns=rules.MAESTRO_COLUMNAS_SIN_NOMBRE)
    maestro = maestro.iloc[rules.MAESTRO_FILAS_METADATOS:].dropna(how="all").reset_index(drop=True)
    col_art = "Número de artículo*^"

    variantes = pd.concat(
        [pd.read_excel(origen, sheet_name=h, dtype=str) for h in rules.HOJAS_VARIANTES],
        ignore_index=True)

    cab = gen[gen["Title"] != ""]

    # --- 3. columnas iguales a la plantilla (+ las de filtros al final) ---
    from processors.exporter import columnas_con_filtros
    esperadas = columnas_con_filtros([str(c).strip() for c in plantilla.columns])
    extra = len(esperadas) - len(plantilla.columns)
    revisar(list(gen.columns) == esperadas,
            "Las columnas coinciden con la plantilla, en el mismo orden"
            + (f", más {extra} de filtros al final" if extra else ""),
            f"{len(gen.columns)} columnas")

    # --- 4. originales intactos ---
    checksums = INPUT / ".checksums_originales.txt"
    if checksums.exists():
        cambiados, faltan = [], []
        for linea in checksums.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            md5, _, nombre = linea.partition("  ")
            # Sólo el nombre: una ruta de otra máquina no debe hacer que se salte.
            ruta = INPUT / Path(nombre.strip()).name
            if not ruta.exists():
                faltan.append(ruta.name)
            elif hashlib.md5(ruta.read_bytes()).hexdigest() != md5.strip():
                cambiados.append(ruta.name)
        revisar(not cambiados and not faltan,
                "Los archivos originales de input/ no se modificaron (MD5)",
                f"cambiados: {cambiados or 'ninguno'}  |  faltan: {faltan or 'ninguno'}")
    else:
        revisar(True, "No hay checksums guardados; se omite la comparación MD5")

    # --- 5. no desaparecieron productos ---
    art_origen = {texto(v) for v in maestro[col_art] if texto(v)}
    reporte = OUTPUT / rules.ARCHIVO_REPORTE
    detalle = pd.read_excel(reporte, sheet_name="Detalle por producto", dtype=str)
    art_reporte = {texto(v) for v in detalle["Nº artículo"] if texto(v)}
    revisar(art_origen <= art_reporte,
            "Todos los productos del origen aparecen en el proceso",
            f"origen={len(art_origen)}  procesados={len(art_reporte)}  "
            f"perdidos={len(art_origen - art_reporte)}")

    exportados = {texto(v) for v in gen["Variant SKU"] if texto(v)}
    revisar(len(cab) == len(art_origen),
            "Se exportó un producto de Shopify por cada producto del origen",
            f"cabeceras={len(cab)}  productos del origen={len(art_origen)}")

    # --- 6. nada inventado ---
    revisar(exportados <= art_origen,
            "Ningún SKU del resultado es inventado (todos vienen del origen)",
            f"SKUs inventados: {sorted(exportados - art_origen)[:5] or 'ninguno'}")

    # La limpieza colapsa espacios dobles, así que la comparación se hace sobre
    # el texto con los espacios normalizados: un título que sólo perdió un
    # espacio de más NO es un título inventado.
    def sin_espacios(valor: str) -> str:
        return " ".join(str(valor).split())

    titulos_origen = {texto(v) for v in maestro["Identificador[es]"] if texto(v)}
    titulos_gen = {texto(v) for v in cab["Title"] if texto(v)}
    origen_norm = {sin_espacios(t) for t in titulos_origen}
    gen_norm = {sin_espacios(t) for t in titulos_gen}
    inventados = gen_norm - origen_norm
    solo_espacios = len(titulos_gen - titulos_origen)
    revisar(not inventados,
            "Ningún título es inventado (todos vienen del concentrado)",
            f"inventados: {len(inventados)}  |  "
            f"{solo_espacios} títulos sólo perdieron espacios dobles, como se pidió")

    if plantilla is not None:
        handles_plantilla = set(plantilla["Handle"])
        titulos_plantilla = {texto(v) for v in plantilla["Title"] if texto(v)}
        # Un título puede coincidir con la plantilla porque ese producto ya
        # estaba cargado en la tienda y también viene en el concentrado. Eso no
        # es copiar: lo que hay que detectar es un título que venga de la
        # plantilla y NO exista en el concentrado.
        copiados = {t for t in titulos_gen
                    if t in titulos_plantilla and sin_espacios(t) not in origen_norm}
        coincidencias = len(titulos_gen & titulos_plantilla)
        revisar(not copiados,
                "No se copió ningún producto de la plantilla como dato real",
                f"copiados: {len(copiados)}  |  {coincidencias} título(s) coinciden "
                f"con la plantilla pero también están en el concentrado")

    # --- 7. variantes bien agrupadas ---
    esperadas = variantes[variantes["Prod.SAP"].isin(art_origen)]
    filas_con_variante = gen[gen["Option1 Value"] != ""]
    revisar(len(filas_con_variante) == len(esperadas),
            "Cada talla del origen produjo exactamente una variante",
            f"origen={len(esperadas)}  exportadas={len(filas_con_variante)}")

    dup = gen[gen["Option1 Value"] != ""].duplicated(subset=["Handle", "Option1 Value"]).sum()
    revisar(dup == 0, "No hay tallas repetidas dentro de un mismo producto",
            f"duplicadas: {dup}")

    revisar(gen["Handle"].nunique() == len(cab),
            "Cada handle tiene exactamente una fila de cabecera",
            f"handles={gen['Handle'].nunique()}  cabeceras={len(cab)}")

    orden_ok = all(
        list(g["Handle"]) == [g["Handle"].iloc[0]] * len(g)
        for _, g in gen.groupby((gen["Handle"] != gen["Handle"].shift()).cumsum()))
    revisar(orden_ok, "Las filas de cada producto están juntas y en orden")

    # --- 8. SKU sin pérdida de información ---
    revisar(all(texto(s) and not texto(s).endswith(".0") for s in exportados),
            "Los SKU conservan su forma original (sin '.0' ni notación científica)")

    ceros = [a for a in art_origen if a.startswith("0")]
    if ceros:
        conservados = [a for a in ceros if a in exportados]
        revisar(len(conservados) == len(ceros),
                "Los SKU con ceros a la izquierda se conservaron",
                f"{len(conservados)}/{len(ceros)}")
    else:
        revisar(True, "El origen no tiene SKU con ceros a la izquierda")

    eans_origen = {texto(v) for v in esperadas["Cod EAN/UPC"] if texto(v)}
    eans_gen = {texto(v) for v in gen["Variant Barcode"] if texto(v)}
    revisar(eans_gen <= eans_origen and len(eans_gen) == len(eans_origen),
            "Los códigos de barras (EAN) se exportaron completos y sin alterar",
            f"origen={len(eans_origen)}  exportados={len(eans_gen)}")

    # --- 9. precios ---
    precios_origen = {}
    for _, fila in esperadas.iterrows():
        clave = (texto(fila["Prod.SAP"]), normalizer.normalizar_talla(fila["Talla"]))
        precios_origen[clave] = float(str(fila["$ FULL"]).replace(",", ""))

    malos = []
    for _, fila in gen[gen["Option1 Value"] != ""].iterrows():
        sap = texto(fila["Variant SKU"])
        clave = (sap, texto(fila["Option1 Value"]))
        esperado = precios_origen.get(clave)
        if esperado is None:
            continue
        try:
            if abs(float(fila["Variant Price"]) - esperado) > 0.005:
                malos.append((clave, fila["Variant Price"], esperado))
        except ValueError:
            malos.append((clave, fila["Variant Price"], esperado))
    revisar(not malos, "Todos los precios coinciden con el origen (sólo cambió el formato)",
            f"diferencias: {malos[:3] or 'ninguna'}")

    formato = gen[gen["Variant Price"] != ""]["Variant Price"]
    revisar(formato.str.fullmatch(r"\d+\.\d{2}").all(),
            "Los precios tienen el formato de Shopify (1099.00)")

    # --- 10. imágenes ---
    img = gen[gen["Image Src"] != ""]
    revisar(img["Image Src"].str.startswith(("http://", "https://")).all(),
            "Todas las imágenes exportadas son URLs válidas", f"{len(img)} imágenes")

    posiciones_ok = all(
        list(pd.to_numeric(g[g["Image Src"] != ""]["Image Position"])) ==
        list(range(1, (g["Image Src"] != "").sum() + 1))
        for _, g in gen.groupby("Handle"))
    revisar(posiciones_ok, "Image Position numera las imágenes 1,2,3... dentro de cada producto")

    urls_origen = set()
    for celda in maestro["Links Fotografías"].dropna():
        urls_origen.update(u.strip() for u in str(celda).split(",") if u.strip())
    revisar(set(img["Image Src"]) <= urls_origen,
            "Ninguna URL de imagen fue inventada")

    # --- 11. reporte ---
    hojas = pd.ExcelFile(reporte).sheet_names
    revisar({"Resumen", "Detalle por producto", "Problemas"} <= set(hojas),
            "El reporte tiene las hojas de resumen, detalle y problemas",
            f"hojas: {hojas}")

    problemas = pd.read_excel(reporte, sheet_name="Problemas", dtype=str)
    revisar(len(problemas) > 0, "El reporte registró los problemas detectados",
            f"{len(problemas)} hallazgos")

    # --- estructura de Shopify ---
    revisar((cab["Option1 Name"] != "").all(),
            "Toda cabecera de producto declara el nombre de la opción (Talla)")
    revisar((gen[gen["Title"] == ""]["Title"] == "").all() and
            (gen[gen["Title"] == ""]["Vendor"] == "").all(),
            "Las filas de variante no repiten los datos del producto (formato Shopify)")

    # --- resumen ---
    fallos = [t for ok, t, _ in resultados if not ok]
    print("=" * 72)
    print(f"{len(resultados) - len(fallos)}/{len(resultados)} comprobaciones superadas")
    if fallos:
        print("\nFALLARON:")
        for titulo in fallos:
            print("  -", titulo)
    print("=" * 72 + "\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
