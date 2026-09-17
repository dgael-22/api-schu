# -*- coding: utf-8 -*-
"""
Reclasifica un export de productos de Shopify con el vocabulario cerrado.

    python retaguear.py <export.csv> [salida.csv] [--vocabulario vocabulario.json]

La salida trae, por handle: tags, Vendor, Type y los metafields de los filtros.
Con --vocabulario también escribe el vocabulario en JSON.
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from utils.helpers import consola_utf8                 # noqa: E402

consola_utf8()

from processors import vocabulario                      # noqa: E402
from processors.retaguear import retaguear_export       # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("export")
    p.add_argument("salida", nargs="?", default=str(RAIZ / "output" / "organizacion.csv"))
    p.add_argument("--vocabulario", help="ruta donde escribir vocabulario.json")
    a = p.parse_args()

    res = retaguear_export(Path(a.export), Path(a.salida))
    print(f"Productos: {res.productos}")
    print(f"Tags distintos: {res.tags_antes} -> {res.tags_despues}")
    print(f"A revisión (dos siluetas sin desempate): {res.a_revision}")
    if res.desconocidos:
        print("Tags fuera del vocabulario (no se escriben):")
        for t, n in sorted(res.desconocidos.items(), key=lambda x: -x[1]):
            print(f"  {n:4}  {t}")
    print(f"Salida: {Path(a.salida).resolve()}")

    if a.vocabulario:
        Path(a.vocabulario).write_text(json.dumps(vocabulario.exportar(), ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"Vocabulario: {Path(a.vocabulario).resolve()}")


if __name__ == "__main__":
    main()
