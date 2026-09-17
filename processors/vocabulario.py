# -*- coding: utf-8 -*-
"""
processors/vocabulario.py
=========================
Clasifica los tags de un producto contra el vocabulario cerrado de
`config/rules.py` y resuelve los conflictos de silueta.

Por qué existe: auditando el catálogo real de la tienda aparecieron 1,240 tags
distintos, de los cuales unos 950 eran códigos de artículo y nombres de modelo,
y 396 productos afirmaban dos "categorías" a la vez. La causa no era el
catálogo: era meter cuatro preguntas independientes —forma, corte, altura y
cierre— en una sola clase.

Este módulo no inventa nada. Toma lo que el producto ya trae, lo reparte en su
clase, y cuando dos datos se contradicen deja que mande el título. Si ni así
se resuelve, lo marca para revisión en vez de elegir por su cuenta.
"""
from __future__ import annotations

import re
import unicodedata

from config import rules


# ---------------------------------------------------------------------------
# Índice del vocabulario: alias normalizado -> (clase, tag canónico)
# ---------------------------------------------------------------------------
def _norma(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto).lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(texto.split())


def _construir_indice() -> dict[str, tuple[str, str]]:
    indice: dict[str, tuple[str, str]] = {}
    for clase, valores in rules.TAGS_VOCABULARIO.items():
        for canonico, alias in valores.items():
            indice[_norma(canonico)] = (clase, canonico)
            for uno in alias:
                indice[_norma(uno)] = (clase, canonico)
    return indice


_INDICE = _construir_indice()
_DESCARTES = [(re.compile(patron), motivo) for patron, motivo in rules.TAGS_DESCARTES]


def motivo_descarte(clave: str) -> str | None:
    """Por qué se tira un tag. None si no hay que tirarlo."""
    for patron, motivo in _DESCARTES:
        if patron.search(clave):
            return motivo
    if clave in rules.TAGS_TECNOLOGIAS:
        return "tecnología del fabricante (va en la ficha)"
    if clave in rules.TAGS_ATRIBUTOS:
        return "atributo que no agrupa"
    if len(clave) <= 3:
        return "fragmento de una frase"
    return None


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------
class Clasificacion:
    """Resultado de repartir los tags de un producto en sus clases."""

    def __init__(self) -> None:
        self.por_clase: dict[str, list[str]] = {c: [] for c in rules.TAGS_ORDEN_CLASES}
        self.descartados: list[tuple[str, str]] = []   # (tag, motivo)
        self.desconocidos: list[str] = []
        self.conflicto: list[str] = []                 # siluetas irreconciliables

    def agregar(self, clase: str, valor: str) -> None:
        if valor not in self.por_clase.setdefault(clase, []):
            self.por_clase[clase].append(valor)

    @property
    def tags(self) -> list[str]:
        # Un mismo valor puede caer en dos clases —'Agujetas' es una categoría
        # de accesorio y también una forma de cierre—, así que se deduplica.
        vistos, salida = set(), []
        for clase in rules.TAGS_ORDEN_CLASES:
            for valor in self.por_clase.get(clase, []):
                if valor not in vistos:
                    vistos.add(valor)
                    salida.append(valor)
        return salida

    @property
    def necesita_revision(self) -> bool:
        return bool(self.conflicto)


def clasificar(tags: list[str], titulo: str = "", extra: list[str] | None = None) -> Clasificacion:
    """
    Reparte `tags` (más `extra`, que suele ser el campo Type cuando trae una
    lista) en las clases del vocabulario. `titulo` se usa para desempatar.
    """
    resultado = Clasificacion()
    titulo_norm = _norma(titulo)

    for bruto in list(tags) + list(extra or []):
        bruto = (bruto or "").strip()
        if not bruto:
            continue
        clave = _norma(bruto)
        if clave in _INDICE:
            clase, canonico = _INDICE[clave]
            resultado.agregar(clase, canonico)
            continue
        motivo = motivo_descarte(clave)
        if motivo:
            resultado.descartados.append((bruto, motivo))
        else:
            resultado.desconocidos.append(bruto)

    _cierre_por_titulo(resultado, titulo_norm)
    _tacon_infantil(resultado, titulo_norm)
    _categoria_por_titulo(resultado, titulo_norm)
    _accesorio_solo_en_accesorios(resultado)
    _resolver_silueta(resultado, titulo_norm)
    _completar(resultado, titulo_norm)
    return resultado


def metafields(c: Clasificacion) -> dict[str, list[str]]:
    """Valores de cada metafield de filtro (rules.METAFIELDS_FILTRO) para un producto."""
    salida: dict[str, list[str]] = {}
    for clave, (_nombre, clases) in rules.METAFIELDS_FILTRO.items():
        valores: list[str] = []
        for clase in clases:
            for valor in c.por_clase.get(clase, []):
                if valor not in valores:
                    valores.append(valor)
        salida[clave] = valores
    return salida


def canonico(texto: str, clase: str) -> str | None:
    """El valor canónico de `texto` si pertenece a `clase`; None si no."""
    encontrado = _INDICE.get(_norma(texto))
    return encontrado[1] if encontrado and encontrado[0] == clase else None


def exportar() -> dict:
    """El vocabulario en JSON, para que otros proyectos lean la misma lista."""
    return {
        "orden_clases": list(rules.TAGS_ORDEN_CLASES),
        "clases": {clase: list(valores) for clase, valores in rules.TAGS_VOCABULARIO.items()},
        "metafields": {clave: {"nombre": nombre, "clases": list(clases),
                               "valores": [v for c in clases for v in rules.TAGS_VOCABULARIO.get(c, {})]}
                       for clave, (nombre, clases) in rules.METAFIELDS_FILTRO.items()},
    }


def _tacon_infantil(c: Clasificacion, titulo: str) -> None:
    """En niña y niño "zapatilla" no es tacón: sólo cuenta si el título dice "tacón"."""
    if not getattr(rules, "TAGS_TACON_INFANTIL_SOLO_EN_TITULO", False):
        return
    if "Tacón" not in c.por_clase.get("altura", []):
        return
    generos = c.por_clase.get("genero", [])
    if not any(g in ("Niña", "Niño") for g in generos):
        return
    if re.search(rules.TAGS_TACON_EN_TITULO, titulo):
        return
    c.por_clase["altura"] = [a for a in c.por_clase["altura"] if a != "Tacón"]
    c.descartados.append(("Tacón", "zapatilla infantil sin tacón en el título"))


def _categoria_por_titulo(c: Clasificacion, titulo: str) -> None:
    """En electrónica el título manda sobre el tag, igual que con las siluetas."""
    if "Electrónica" not in c.por_clase.get("tipo", []):
        return
    for nombre, patron in getattr(rules, "TAGS_CATEGORIA_EN_TITULO", ()):
        if re.search(patron, titulo):
            electronica = {n for n, _ in rules.TAGS_CATEGORIA_EN_TITULO}
            previas = [x for x in c.por_clase.get("categoria", []) if x in electronica and x != nombre]
            for x in previas:
                c.descartados.append((x, f"el título dice {nombre}"))
            c.por_clase["categoria"] = [x for x in c.por_clase.get("categoria", []) if x not in previas]
            c.agregar("categoria", nombre)
            return


def _accesorio_solo_en_accesorios(c: Clasificacion) -> None:
    """Un zapato "con Plantilla Hexafoam" no es una plantilla, ni un vestido con cinturón es un cinturón."""
    if not getattr(rules, "TAGS_ACCESORIO_SOLO_EN_ACCESORIOS", False):
        return
    tipos = c.por_clase.get("tipo", [])
    if not tipos or "Accesorios" in tipos:
        return                      # sin tipo no hay con qué contradecir
    siluetas = c.por_clase.get("silueta", [])
    for s in siluetas:
        if s not in _SILUETAS_CALZADO:
            c.descartados.append((s, f"categoría de accesorio en un producto de {tipos[0]}"))
    c.por_clase["silueta"] = [s for s in siluetas if s in _SILUETAS_CALZADO]


def _cierre_por_titulo(c: Clasificacion, titulo: str) -> None:
    """'Slip On' y 'pulsera' no son siluetas: son cierres, y viven en el título."""
    if "Calzado" not in c.por_clase.get("tipo", []):
        return                      # una agujeta suelta no "se cierra" con nada
    for nombre, patron in rules.TAGS_CIERRE_EN_TITULO:
        if re.search(patron, titulo):
            c.agregar("cierre", nombre)


_SILUETAS_CALZADO = ("Botas y Botines", "Tenis", "Sandalias",
                     "Mocasines", "Flats y Balerinas", "Zapatos")


def _resolver_silueta(c: Clasificacion, titulo: str) -> None:
    siluetas = [s for s in c.por_clase.get("silueta", []) if s in _SILUETAS_CALZADO]
    if len(siluetas) < 2:
        return

    elegida = None
    for nombre, patron in rules.TAGS_SILUETA_EN_TITULO:
        if re.search(patron, titulo) and nombre in siluetas:
            elegida = nombre
            break
    if elegida is None and "Zapatos" in siluetas and len(siluetas) == 2:
        # 'Zapato' es genérico: pierde contra cualquier forma específica.
        elegida = next(s for s in siluetas if s != "Zapatos")

    if elegida is None:
        if rules.TAGS_DETENER_SI_HAY_CONFLICTO:
            c.conflicto = siluetas
        return

    c.por_clase["silueta"] = [
        s for s in c.por_clase["silueta"]
        if s not in _SILUETAS_CALZADO or s == elegida
    ]


def _completar(c: Clasificacion, titulo: str) -> None:
    tipos = c.por_clase.get("tipo", [])

    if not c.por_clase.get("genero"):
        for nombre, patron in rules.TAGS_GENERO_EN_TITULO:
            if re.search(patron, titulo):
                c.agregar("genero", nombre)
                break

    if (rules.TAGS_ACCESORIO_SIN_GENERO_ES_UNISEX
            and "Accesorios" in tipos and not c.por_clase.get("genero")):
        c.agregar("genero", "Unisex")

    if "Accesorios" in tipos and not c.por_clase.get("silueta"):
        for nombre, patron in getattr(rules, "TAGS_ACCESORIO_EN_TITULO", ()):
            if re.search(patron, titulo):
                c.agregar("silueta", nombre)
                break

    if "Calzado" in tipos and rules.TAGS_CALZADO_SIN_SILUETA:
        if not any(s in _SILUETAS_CALZADO for s in c.por_clase.get("silueta", [])):
            c.agregar("silueta", rules.TAGS_CALZADO_SIN_SILUETA)
