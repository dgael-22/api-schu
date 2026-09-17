# -*- coding: utf-8 -*-
"""
processors/retaguear.py
=======================
Pasa un export de productos de Shopify por el vocabulario cerrado y escribe,
por handle, lo que cada producto debe tener en la tienda: tags, Vendor, Type y
los metafields de los filtros.

No genera un CSV para importar en Shopify —un CSV parcial hace creer a Shopify
que el producto perdió sus variantes—. La salida la consume el middleware
(`npm run shopify:organizar`), que escribe por la API campo por campo.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config import rules
from processors import vocabulario

COLUMNAS = ["Handle", "Title", "Vendor", "Type", "Tags",
            *rules.METAFIELDS_FILTRO.keys(), "Revision", "Descartados", "Desconocidos"]


@dataclass
class Resultado:
    productos: int = 0
    a_revision: int = 0
    tags_antes: int = 0
    tags_despues: int = 0
    desconocidos: dict[str, int] = field(default_factory=dict)


def retaguear_export(ruta_csv: Path, ruta_salida: Path) -> Resultado:
    df = pd.read_csv(ruta_csv, dtype=str, keep_default_na=False)
    productos = df[df["Title"].str.strip() != ""]
    res = Resultado(productos=len(productos))
    antes, despues = set(), set()

    filas = []
    for _, f in productos.iterrows():
        tags = [t.strip() for t in f["Tags"].split(",") if t.strip()]
        antes.update(tags)
        # El Type suele traer la familia ('calzado-caballero'): se suma como
        # pista, igual que en el procesador.
        tipo = f.get("Type", "").strip()
        extra = [tipo] + (tipo.split("-") if "-" in tipo else [])
        c = vocabulario.clasificar(tags, f["Title"], extra)
        despues.update(c.tags)
        if c.necesita_revision:
            res.a_revision += 1
        for d in c.desconocidos:
            res.desconocidos[d] = res.desconocidos.get(d, 0) + 1

        tipos = c.por_clase.get("tipo", [])
        vendor = f.get("Vendor", "").strip()
        mf = vocabulario.metafields(c)
        filas.append({
            "Handle": f["Handle"],
            "Title": f["Title"],
            "Vendor": vocabulario.canonico(vendor, "marca") or vendor,
            "Type": tipos[0] if tipos else f.get("Type", ""),
            "Tags": ", ".join(c.tags),
            **{k: " | ".join(v) for k, v in mf.items()},
            "Revision": " / ".join(c.conflicto),
            "Descartados": "; ".join(f"{t} ({m})" for t, m in c.descartados),
            "Desconocidos": "; ".join(c.desconocidos),
        })

    res.tags_antes, res.tags_despues = len(antes), len(despues)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with ruta_salida.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    return res
