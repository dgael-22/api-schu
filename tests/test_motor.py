# -*- coding: utf-8 -*-
"""Pruebas del motor: la regla de no pisar datos y el registro de origen."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from enriquecedor import Ficha, Motor, Solicitud, aplicar   # noqa: E402
from enriquecedor.base import FuenteMarca                    # noqa: E402


class FuenteDePrueba(FuenteMarca):
    """Fuente falsa: devuelve lo que se le diga, sin tocar la red."""
    nombre = "prueba"
    sitio = "https://ejemplo.test"

    def __init__(self, fichas=None, truena=False):
        self.fichas = fichas or {}
        self.truena = truena
        self.preparada = False
        self.cerrada = False

    def preparar(self):
        self.preparada = True

    def cerrar(self):
        self.cerrada = True

    def buscar(self, solicitud):
        if self.truena:
            raise RuntimeError("se cayó el sitio")
        for llave in solicitud.llaves():
            if llave in self.fichas:
                return self.fichas[llave]
        return None


class TestAplicar(unittest.TestCase):
    def test_no_pisa_lo_que_ya_existe(self):
        producto = {"titulo": "El que mandó el proveedor", "descripcion": ""}
        ficha = Ficha(titulo="El de la marca", descripcion="Descripción nueva",
                      fuente="prueba", url_fuente="https://ejemplo.test/x")
        llenados = aplicar(producto, ficha)

        self.assertEqual(producto["titulo"], "El que mandó el proveedor")
        self.assertEqual(producto["descripcion"], "Descripción nueva")
        self.assertEqual(llenados, ["descripcion"])

    def test_marca_el_producto_como_borrador(self):
        producto = {}
        aplicar(producto, Ficha(titulo="X", fuente="prueba", url_fuente="u"))
        self.assertEqual(producto["estatus"], "draft")

    def test_registra_origen_url_y_fecha(self):
        producto = {}
        aplicar(producto, Ficha(titulo="X", fuente="flexi",
                                url_fuente="https://flexi.com.mx/p"))
        self.assertEqual(producto["_origen_datos"], "flexi")
        self.assertEqual(producto["_url_origen"], "https://flexi.com.mx/p")
        self.assertTrue(producto["_enriquecido_en"])
        self.assertIn("titulo", producto["_campos_enriquecidos"])

    def test_sin_nada_que_llenar_no_ensucia_el_producto(self):
        producto = {"titulo": "Ya estaba"}
        llenados = aplicar(producto, Ficha(titulo="Otro"))
        self.assertEqual(llenados, [])
        self.assertNotIn("_origen_datos", producto)
        self.assertNotIn("estatus", producto)


class TestMotor(unittest.TestCase):
    def test_encuentra_por_ean(self):
        ficha = Ficha(titulo="Botín", imagenes=["u1"], url_fuente="u")
        fuente = FuenteDePrueba({"7500000000001": ficha})
        s = Solicitud(articulo="139000", marca="prueba", eans=["7500000000001"])

        r = Motor({"prueba": fuente}).enriquecer([s])[0]
        self.assertTrue(r.encontrado)
        self.assertEqual(r.ficha.titulo, "Botín")

    def test_reporta_el_que_no_existe(self):
        r = Motor({"prueba": FuenteDePrueba({})}).enriquecer(
            [Solicitud(articulo="1", marca="prueba")])[0]
        self.assertFalse(r.encontrado)
        self.assertIn("no publica", r.motivo)

    def test_marca_sin_fuente_no_truena(self):
        r = Motor({}).enriquecer([Solicitud(articulo="1", marca="onena")])[0]
        self.assertFalse(r.encontrado)
        self.assertIn("sin fuente", r.motivo)

    def test_un_error_de_la_fuente_no_tumba_el_lote(self):
        motor = Motor({"prueba": FuenteDePrueba(truena=True)})
        rs = motor.enriquecer([Solicitud(articulo=str(i), marca="prueba") for i in range(3)])
        self.assertEqual(len(rs), 3)
        self.assertTrue(all("error de la fuente" in r.motivo for r in rs))

    def test_siempre_cierra_la_fuente(self):
        fuente = FuenteDePrueba(truena=True)
        Motor({"prueba": fuente}).enriquecer([Solicitud(articulo="1", marca="prueba")])
        self.assertTrue(fuente.preparada)
        self.assertTrue(fuente.cerrada)

    def test_anota_discrepancias(self):
        ficha = Ficha(titulo="Botín Negro", color="Negro", url_fuente="u")
        motor = Motor({"prueba": FuenteDePrueba({"1": ficha})})
        motor.enriquecer([Solicitud(articulo="1", marca="prueba", color="Chocolate")])

        self.assertEqual(len(motor.discrepancias), 1)
        self.assertEqual(motor.discrepancias[0]["campo"], "color")
        self.assertEqual(motor.discrepancias[0]["en_el_excel"], "Chocolate")

    def test_respeta_el_limite(self):
        fuente = FuenteDePrueba({})
        rs = Motor({"prueba": fuente}, limite=2).enriquecer(
            [Solicitud(articulo=str(i), marca="prueba") for i in range(10)])
        self.assertEqual(len(rs), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestLimitePriorizaFuentes(unittest.TestCase):
    """El tope de --limite no debe gastarse en marcas sin adaptador."""

    def test_prefiere_las_marcas_con_fuente(self):
        ficha = Ficha(titulo="Botín", url_fuente="u")
        motor = Motor({"prueba": FuenteDePrueba({"con": ficha})}, limite=1)
        rs = motor.enriquecer([
            Solicitud(articulo="sin", marca="onena"),      # sin fuente, va primero
            Solicitud(articulo="con", marca="prueba"),     # con fuente
        ])
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0].solicitud.articulo, "con")
        self.assertTrue(rs[0].encontrado)

    def test_sin_limite_procesa_todo(self):
        motor = Motor({"prueba": FuenteDePrueba({})})
        rs = motor.enriquecer([Solicitud(articulo="a", marca="onena"),
                               Solicitud(articulo="b", marca="prueba")])
        self.assertEqual(len(rs), 2)
