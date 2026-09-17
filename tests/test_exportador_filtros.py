# -*- coding: utf-8 -*-
"""Columnas de filtros (metafields) en el CSV del Excel. Ninguna prueba toca la red."""
import unittest

from config import rules
from processors import exporter
from processors.products import Producto, Variante


def _producto(**kw) -> Producto:
    base = dict(handle="botin-flexi-cafe", titulo="Botín de Tacón Flexi para Mujer con Agujetas",
                vendor="Flexi", tipo="Calzado",
                tags="Flexi, Dama, Calzado, Botas y Botines, Tacón, Agujetas, Casual, Piel, Café",
                variantes=[Variante(talla="23", sku="1"), Variante(talla="24", sku="2")])
    base.update(kw)
    return Producto(**base)


class TestColumnasFiltros(unittest.TestCase):

    def test_encabezados_con_formato_de_shopify(self):
        cols = exporter.columnas_filtros()
        self.assertEqual(len(cols), len(rules.METAFIELDS_FILTRO))
        self.assertIn("Categoría (product.metafields.custom.categoria)", cols)
        self.assertIn("Tacón (product.metafields.custom.altura)", cols)

    def test_van_al_final_sin_mover_la_plantilla(self):
        plantilla = ["Handle", "Title", "Tags", "Status"]
        salida = exporter.columnas_con_filtros(plantilla)
        self.assertEqual(salida[:4], plantilla)
        self.assertEqual(salida[4:], exporter.columnas_filtros())

    def test_no_duplica_si_la_plantilla_ya_las_trae(self):
        plantilla = ["Handle"] + exporter.columnas_filtros()
        self.assertEqual(exporter.columnas_con_filtros(plantilla), plantilla)

    def test_valores_en_la_primera_fila_y_vacios_en_las_variantes(self):
        cols = exporter.columnas_con_filtros(["Handle", "Title", "Tags", "Status", "Variant SKU"])
        df = exporter.construir_filas([_producto()], cols)
        primera, segunda = df.iloc[0], df.iloc[1]
        self.assertEqual(primera["Género (product.metafields.custom.genero)"], "Dama")
        self.assertEqual(primera["Categoría (product.metafields.custom.categoria)"], "Botas y Botines")
        self.assertEqual(primera["Tacón (product.metafields.custom.altura)"], "Tacón")
        self.assertEqual(primera["Cierre (product.metafields.custom.cierre)"], "Agujetas")
        self.assertEqual(primera["Material (product.metafields.custom.material)"], "Piel")
        self.assertTrue(all(segunda[c] == "" for c in exporter.columnas_filtros()))

    def test_varios_valores_separados_con_punto_y_coma(self):
        p = _producto(titulo="Zapato Escolar Coqueta para niña", tags="Coqueta, Niña, Infantil, Escolar, Calzado, Zapatos")
        v = exporter.valores_filtros(p)
        self.assertEqual(v["Etapa (product.metafields.custom.etapa)"], "Infantil; Escolar")

    def test_valores_siempre_dentro_de_las_listas_cerradas(self):
        from processors import vocabulario
        permitidos = {k: set(d["valores"]) for k, d in vocabulario.exportar()["metafields"].items()}
        v = exporter.valores_filtros(_producto())
        for clave in rules.METAFIELDS_FILTRO:
            celda = next(val for col, val in v.items() if col.endswith(f".{clave})"))
            for valor in filter(None, celda.split(rules.METAFIELDS_SEPARADOR_CSV)):
                self.assertIn(valor, permitidos[clave])

    def test_apagado_no_agrega_nada(self):
        original = rules.METAFIELDS_EN_CSV
        rules.METAFIELDS_EN_CSV = False
        try:
            self.assertEqual(exporter.columnas_filtros(), [])
            self.assertEqual(exporter.valores_filtros(_producto()), {})
        finally:
            rules.METAFIELDS_EN_CSV = original


if __name__ == "__main__":
    unittest.main()
