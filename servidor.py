# -*- coding: utf-8 -*-
"""
servidor.py
===========
Arranca la API.

    python servidor.py                 http://127.0.0.1:8000
    python servidor.py --puerto 9000
    python servidor.py --publico       accesible desde otras máquinas de la red
    python servidor.py --recargar      se reinicia solo al editar el código

Equivale a `uvicorn api.app:app`, pero sin tener que recordar el comando.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))


def main() -> int:
    parser = argparse.ArgumentParser(description="Arranca la API del procesador.")
    parser.add_argument("--puerto", type=int, default=8000)
    parser.add_argument("--host", default=None)
    parser.add_argument("--publico", action="store_true",
                        help="escuchar en 0.0.0.0 (visible desde la red local)")
    parser.add_argument("--recargar", action="store_true",
                        help="reiniciar automáticamente al cambiar el código")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Falta uvicorn. Instala las dependencias con:\n"
              "    pip install -r requirements.txt")
        return 1

    host = args.host or ("0.0.0.0" if args.publico else "127.0.0.1")
    visible = "127.0.0.1" if host in ("127.0.0.1", "0.0.0.0") else host

    print()
    print("=" * 62)
    print("  API del procesador de catálogos para Shopify")
    print("=" * 62)
    print(f"  Página     http://{visible}:{args.puerto}")
    print(f"  Docs       http://{visible}:{args.puerto}/docs")
    print("  Detener    Ctrl + C")
    print("=" * 62)
    print()

    uvicorn.run("api.app:app", host=host, port=args.puerto,
                reload=args.recargar, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
