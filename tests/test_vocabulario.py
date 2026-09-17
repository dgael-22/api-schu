# -*- coding: utf-8 -*-
"""Pruebas del vocabulario cerrado. Ninguna toca la red."""
import unittest

from processors import vocabulario as v


def tags(lista, titulo="", extra=None):
    return v.clasificar(lista, titulo, extra)


class TestVocabulario(unittest.TestCase):

    def test_mayusculas_se_vuelven_canonicas(self):
        # Shopify distingue mayúsculas: 'CABALLERO' no entra a la colección Caballero.
        c = tags(["CABALLERO", "QUIRELLI", "CALZADO", "TENIS"], "Tenis Quirelli para hombre")
        self.assertEqual(c.tags[:4], ["Quirelli", "Caballero", "Calzado", "Tenis"])

    def test_codigos_y_capturas_no_son_tags(self):
        c = tags(["Calzado", "136707", "capturafebrero2026", "CPS_53111600", "CU_H87"], "Zapato Flexi")
        self.assertNotIn("136707", c.tags)
        self.assertEqual({m for _, m in c.descartados} >= {"código de artículo", "marca de captura o lote",
                                                            "código interno de Hybris"}, True)

    def test_zapato_con_plantilla_no_es_plantilla(self):
        c = tags(["Quirelli", "Caballero", "Calzado", "Plantillas", "Zapatos"],
                 "Zapato Casual Quirelli Con Plantilla Hexafoam Para Hombre")
        self.assertNotIn("Plantillas", c.tags)
        self.assertIn("Zapatos", c.tags)

    def test_ropa_con_cinturon_no_es_cinturon(self):
        c = tags(["Coqueta", "Niña", "Ropa", "Cinturones", "Casual"], "Vestido Coqueta para niña con cinturón")
        self.assertNotIn("Cinturones", c.tags)
        self.assertIn("Ropa", c.tags)

    def test_plantilla_accesorio_si_es_plantilla(self):
        c = tags(["Flexi", "Accesorios"], "Plantilla Walking Soft Coregel Flexi")
        self.assertIn("Plantillas", c.tags)
        self.assertIn("Unisex", c.tags)

    def test_el_titulo_desempata_la_silueta(self):
        c = tags(["Calzado", "Tenis", "Botas y Botines"], "Botín Casual Flexi para Mujer")
        self.assertIn("Botas y Botines", c.tags)
        self.assertNotIn("Tenis", c.tags)

    def test_dos_siluetas_sin_desempate_van_a_revision(self):
        c = tags(["Calzado", "Tenis", "Sandalias"], "Modelo Kindra Flexi")
        self.assertTrue(c.necesita_revision)

    def test_zapato_generico_pierde(self):
        c = tags(["Calzado", "Zapatos", "Mocasines"], "Modelo Diego Quirelli")
        self.assertEqual([s for s in c.por_clase["silueta"]], ["Mocasines"])

    def test_calzado_sin_silueta_es_zapatos(self):
        c = tags(["Calzado", "Dama"], "Modelo Anansa")
        self.assertIn("Zapatos", c.tags)

    def test_subcategorias_de_electronica_y_ropa(self):
        c = tags(["Lg", "Electrónica", "Audio"], "Bocina LG XBOOM")
        self.assertEqual(c.tags, ["LG", "Electrónica", "Audio"])
        c = tags(["Coqueta", "Niña", "Ropa", "Jeans y Pantalones"], "Jeans Coqueta")
        self.assertIn("Shorts y Pantalones", c.tags)

    def test_en_electronica_manda_el_titulo(self):
        casos = {
            "Apple Watch Series 11 GPS con Caja de Aluminio, Pantalla Siempre Activa": "Relojes y Wearables",
            "iPhone 17 256 GB:Pantalla de 6.3 Pulgadas con Promotion": "Celulares",
            "Galaxy-Tab-A9 8.7\" 64 GB": "Cómputo",
            "Smart TV 32 pulgadas pantalla Android TV Audio HD Bluetooth": "Pantallas y TV",
            "LG Soundbar con AI Sound Pro de 2.1 Canales S40T": "Audio",
        }
        for titulo, esperada in casos.items():
            c = tags(["Electrónica", "Pantallas y TV"], titulo)
            self.assertEqual(c.por_clase["categoria"], [esperada], titulo)

    def test_zapatilla_de_nina_no_es_tacon(self):
        c = tags(["Coqueta", "Niña", "Calzado", "Flats y Balerinas", "Zapatilla"],
                 "Zapatilla Coqueta para niña en charol negro Miranda con flores decorativas")
        self.assertNotIn("Tacón", c.tags)
        self.assertIn("Flats y Balerinas", c.tags)

    def test_nina_con_tacon_en_el_titulo_si_es_tacon(self):
        c = tags(["Coqueta", "Niña", "Calzado", "Tacón"], "Zapato de tacón Coqueta para niña")
        self.assertIn("Tacón", c.tags)

    def test_zapatilla_de_dama_sigue_siendo_tacon(self):
        c = tags(["Quirelli", "Dama", "Calzado", "Zapatilla"], "Zapatilla Puntal Quirelli para Mujer")
        self.assertIn("Tacón", c.tags)

    def test_temporadas_viejas_se_reconocen(self):
        self.assertIn("OI18", tags(["Calzado", "OI18"], "Bota Audaz").tags)

    def test_metafields_de_filtro(self):
        c = tags(["Flexi", "Dama", "Calzado", "Botas y Botines", "Tacón", "Casual", "Piel"],
                 "Botín de Tacón Flexi para Mujer con Agujetas")
        mf = v.metafields(c)
        self.assertEqual(mf["genero"], ["Dama"])
        self.assertEqual(mf["categoria"], ["Botas y Botines"])
        self.assertEqual(mf["altura"], ["Tacón"])
        self.assertEqual(mf["cierre"], ["Agujetas"])
        self.assertEqual(mf["ocasion"], ["Casual"])

    def test_es_idempotente(self):
        entrada = ["FLEXI", "mujer", "calzado", "sneaker", "Plantillas", "NEGRO", "PV25", "141202"]
        titulo = "Sneaker Flexi para Mujer Estilo 141202 Negro"
        una = tags(entrada, titulo).tags
        self.assertEqual(tags(una, titulo).tags, una)

    def test_exportar_trae_los_valores_de_cada_filtro(self):
        e = v.exportar()
        self.assertIn("Tenis", e["metafields"]["categoria"]["valores"])
        self.assertIn("Celulares", e["metafields"]["categoria"]["valores"])
        self.assertEqual(e["metafields"]["ocasion"]["nombre"], "Ocasión")


if __name__ == "__main__":
    unittest.main()
