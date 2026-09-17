# -*- coding: utf-8 -*-
"""
api/trabajos.py
===============
Registro en memoria de los trabajos de procesamiento.

Cada archivo que se sube crea un trabajo con su propia carpeta temporal, así
que dos personas pueden procesar catálogos distintos a la vez sin pisarse.
Los trabajos viejos se borran solos.

Es deliberadamente simple: un diccionario protegido por un candado. Cuando
haga falta que sobreviva a un reinicio del servidor, este es el único módulo
que hay que cambiar por una base de datos.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Estados posibles
EN_COLA = "en_cola"
PROCESANDO = "procesando"
TERMINADO = "terminado"
FALLIDO = "fallido"


@dataclass
class Trabajo:
    id: str
    nombre_archivo: str
    estado: str = EN_COLA
    mensaje: str = "En cola"
    creado: float = field(default_factory=time.time)
    terminado: float | None = None
    carpeta: Path | None = None
    ruta_origen: Path | None = None
    resumen: dict = field(default_factory=dict)
    archivos: dict[str, str] = field(default_factory=dict)   # clave -> nombre

    def a_json(self, base_url: str = "") -> dict:
        descargas = {}
        if self.estado == TERMINADO:
            for clave, nombre in self.archivos.items():
                descargas[clave] = f"{base_url}/api/trabajos/{self.id}/descargar/{clave}"
            descargas["zip"] = f"{base_url}/api/trabajos/{self.id}/descargar/zip"
        return {
            "id": self.id,
            "archivo": self.nombre_archivo,
            "estado": self.estado,
            "mensaje": self.mensaje,
            "creado": self.creado,
            "segundos": (round((self.terminado or time.time()) - self.creado, 2)),
            "resumen": self.resumen,
            "descargas": descargas,
        }


class Registro:
    """Guarda los trabajos y limpia los caducados."""

    def __init__(self, carpeta_base: Path, vida_segundos: int = 3600,
                 maximo: int = 50):
        self.carpeta_base = carpeta_base
        self.carpeta_base.mkdir(parents=True, exist_ok=True)
        self.vida_segundos = vida_segundos
        self.maximo = maximo
        self._trabajos: dict[str, Trabajo] = {}
        self._candado = threading.Lock()

    def crear(self, nombre_archivo: str) -> Trabajo:
        self.limpiar()
        identificador = uuid.uuid4().hex[:12]
        carpeta = self.carpeta_base / identificador
        (carpeta / "entrada").mkdir(parents=True, exist_ok=True)
        (carpeta / "salida").mkdir(parents=True, exist_ok=True)
        trabajo = Trabajo(id=identificador, nombre_archivo=nombre_archivo,
                          carpeta=carpeta)
        with self._candado:
            self._trabajos[identificador] = trabajo
        return trabajo

    def obtener(self, identificador: str) -> Trabajo | None:
        with self._candado:
            return self._trabajos.get(identificador)

    def listar(self) -> list[Trabajo]:
        with self._candado:
            return sorted(self._trabajos.values(), key=lambda t: -t.creado)

    def borrar(self, identificador: str) -> bool:
        with self._candado:
            trabajo = self._trabajos.pop(identificador, None)
        if trabajo is None:
            return False
        if trabajo.carpeta and trabajo.carpeta.exists():
            shutil.rmtree(trabajo.carpeta, ignore_errors=True)
        return True

    def limpiar(self) -> int:
        """Borra los trabajos caducados y los que sobran del límite."""
        ahora = time.time()
        with self._candado:
            caducados = [t for t in self._trabajos.values()
                         if ahora - t.creado > self.vida_segundos]
            vivos = sorted((t for t in self._trabajos.values() if t not in caducados),
                           key=lambda t: -t.creado)
            sobrantes = vivos[self.maximo:]
            a_borrar = caducados + sobrantes
            for trabajo in a_borrar:
                self._trabajos.pop(trabajo.id, None)

        for trabajo in a_borrar:
            if trabajo.carpeta and trabajo.carpeta.exists():
                shutil.rmtree(trabajo.carpeta, ignore_errors=True)
        return len(a_borrar)
