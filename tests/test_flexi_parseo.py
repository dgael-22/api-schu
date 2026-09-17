# -*- coding: utf-8 -*-
"""Pruebas del parseo de Flexi contra HTML real capturado del sitio."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from enriquecedor.fuentes import flexi_parseo as p          # noqa: E402
from tests.fixture_flexi import FICHA, FICHA_TEXTO, LISTADO  # noqa: E402


class TestListado(unittest.TestCase):
    def setUp(self):
        self.enlaces = p.extraer_enlaces_producto(LISTADO)

    def test_encuentra_todos_los_productos(self):
        self.assertEqual(len(self.enlaces), 4)

    def test_saca_el_ean_de_la_url(self):
        self.assertEqual(self.enlaces[0].ean, "7500421982280")

    def test_saca_estilo_y_color_del_slug(self):
        primero = self.enlaces[0]
        self.assertEqual(primero.estilo, "138801")
        self.assertEqual(primero.color, "Negro")

    def test_color_compuesto(self):
        enlaces = p.extraer_enlaces_producto(
            '<a href="/es/producto/7500000000001-bota-flexi-estilo-99999-rojo-gris">x</a>')
        self.assertEqual(enlaces[0].color, "Rojo - Gris")

    def test_no_repite_el_mismo_ean(self):
        doble = LISTADO + LISTADO
        self.assertEqual(len(p.extraer_enlaces_producto(doble)), 4)

    def test_arma_la_url_absoluta(self):
        self.assertTrue(self.enlaces[0].url.startswith("https://www.flexi.com.mx/es/producto/"))

    def test_html_vacio_no_truena(self):
        self.assertEqual(p.extraer_enlaces_producto(""), [])
        self.assertEqual(p.extraer_enlaces_producto(None), [])


class TestFicha(unittest.TestCase):
    def setUp(self):
        self.ficha = p.parsear_ficha(FICHA, texto_visible=FICHA_TEXTO)

    def test_lee_el_jsonld(self):
        self.assertEqual(self.ficha.ean, "7500421982280")
        self.assertEqual(self.ficha.titulo,
                         "Sneaker Suela Con Gel Flexi para Mujer Estilo 138801 Negro")

    def test_lee_precio_y_moneda(self):
        self.assertEqual(self.ficha.precio, "1199")
        self.assertEqual(self.ficha.moneda, "MXN")

    def test_saca_estilo_y_color_del_titulo(self):
        self.assertEqual(self.ficha.estilo, "138801")
        self.assertEqual(self.ficha.color, "Negro")

    def test_cruza_ean_con_numero_sap(self):
        # Éste es el puente con el concentrado: sin él no hay enriquecimiento.
        self.assertEqual(self.ficha.articulo, "1390037904")

    def test_trae_las_imagenes_del_color_correcto(self):
        self.assertEqual(len(self.ficha.imagenes), 6)
        self.assertTrue(all("138801-negro" in u for u in self.ficha.imagenes))

    def test_descarta_las_imagenes_de_otro_color(self):
        self.assertFalse(any("rosa" in u for u in self.ficha.imagenes))

    def test_conserva_el_token_context(self):
        # Sin el token la URL no sirve: no se puede recortar.
        self.assertIn("?context=", self.ficha.imagenes[0])

    def test_ficha_vacia_no_truena(self):
        vacia = p.parsear_ficha("<html></html>")
        self.assertEqual(vacia.titulo, "")
        self.assertEqual(vacia.imagenes, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
