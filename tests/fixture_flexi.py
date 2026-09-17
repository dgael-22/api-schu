# -*- coding: utf-8 -*-
"""
Fragmentos de HTML REALES de flexi.com.mx, capturados el 7-sep-2026 con el
navegador. No están inventados: son recortes de la tarjeta de producto del
listado de Ofertas y de la ficha del estilo 138801 negro.
"""

# Tarjeta del listado, tal como la sirve el sitio (recortada, sin los atributos
# _ngcontent que Angular agrega y que no aportan nada al parseo).
LISTADO = '''
<div class="product-item">
  <a tabindex="0" href="/es/producto/7500421982280-sneaker-suela-con-gel-flexi-para-mujer-estilo-138801-negro">
    <div class="product-image-container">
      <cx-media class="sale-chip"><img alt="Oferta flexi"
        src="https://apiecom.flexi.com.mx/medias/20211227-LOGO-REBAJAS-ES-3-.png?context=bWFzdGVy"></cx-media>
      <img src="https://apiecom.flexi.com.mx/medias/138801-negro-lateral.jpg?context=bWFzdGVyfGltYWdlc3w">
      <img src="https://apiecom.flexi.com.mx/medias/138801-rosa-lateral.jpg?context=bWFzdGVyfGltYWdlc3x">
    </div>
    <div class="product-name">Sneaker Suela Con Gel Flexi para Mujer Estilo 138801 Negro</div>
    <div class="price">$1,199.00 MXN</div><div class="price-discount">$1,019.15 MXN</div>
  </a>
</div>
<div class="product-item">
  <a href="/es/producto/7500421753132-sneaker-valvula-de-aire-flexi-para-mujer-estilo-131501-gris">
    <img src="https://apiecom.flexi.com.mx/medias/131501-gris-lateral.jpg?context=bWFzdGVy">
  </a>
</div>
<div class="product-item">
  <a href="/es/producto/7500421982518-sneaker-suela-con-gel-flexi-para-mujer-estilo-138801-rosa">
    <img src="https://apiecom.flexi.com.mx/medias/138801-rosa-lateral.jpg?context=bWFzdGVy">
  </a>
</div>
<a href="/es/producto/7500277072661-calzado-escolar-ajustable-flexi-para-mujer-estilo-131913-negro">otro</a>
'''

# Ficha del producto. El JSON-LD es el que sirve el sitio de verdad.
FICHA = '''
<html><head>
<script type="application/ld+json">
[{"@context":"http://schema.org","@type":"Product","sku":"7500421982280",
"name":"Sneaker Suela Con Gel Flexi para Mujer Estilo 138801 Negro",
"image":"https://apiecom.flexi.com.mx/medias/138801-negro-lateral.jpg?context=bWFzdGVy",
"offers":{"@type":"Offer","availability":"InStock","price":1199,"priceCurrency":"MXN"}}]
</script>
</head><body>
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-lateral.jpg?context=aaa">
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-derecha-par.jpg?context=bbb">
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-interior.jpg?context=ccc">
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-arriba-par.jpg?context=ddd">
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-izquierda.jpg?context=eee">
<img src="https://apiecom.flexi.com.mx/medias/138801-negro-atras.jpg?context=fff">
<img src="https://apiecom.flexi.com.mx/medias/138801-rosa-lateral.jpg?context=ggg">
</body></html>
'''

# innerText de la ficha (recortado). De aquí sale el puente EAN <-> SAP.
FICHA_TEXTO = """Sneaker Suela Con Gel Flexi para Mujer Estilo 138801 Negro
ID 7500421982280 - 1390037904
$1,199.00 MXN$1,019.15 MXN
TALLAS
22 22.5 23 23.5 24 24.5 25 25.5 26 26.5 27"""
