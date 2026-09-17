# -*- coding: utf-8 -*-
"""
api/plantilla_web.py
====================
La página que se ve en la raíz del servidor (http://127.0.0.1:8000 por defecto).

Es un único HTML sin dependencias externas: arrastras el Excel, se sube, se
consulta el estado cada segundo y aparecen los botones de descarga.
"""

PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Procesador de catálogos para Shopify</title>
<style>
  :root{
    --fondo:#f6f7f9; --tarjeta:#fff; --texto:#1a1d21; --suave:#5b6570;
    --borde:#dfe3e8; --acento:#1f3864; --ok:#137a4b; --aviso:#9a6700; --error:#b3261e;
  }
  @media (prefers-color-scheme: dark){
    :root{ --fondo:#14171a; --tarjeta:#1d2126; --texto:#e8eaed; --suave:#9aa4af;
           --borde:#2e343c; --acento:#7aa2e3; --ok:#4ec98a; --aviso:#e0b341; --error:#f2857d; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--fondo);color:var(--texto);
       font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
  .envoltura{max-width:860px;margin:0 auto;padding:32px 20px 64px}
  h1{font-size:24px;margin:0 0 6px}
  .sub{color:var(--suave);margin:0 0 28px}
  .tarjeta{background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;
           padding:22px;margin-bottom:18px}
  .zona{border:2px dashed var(--borde);border-radius:10px;padding:34px 20px;text-align:center;
        cursor:pointer;transition:.15s}
  .zona:hover,.zona.activa{border-color:var(--acento);background:rgba(127,127,127,.06)}
  .zona strong{display:block;font-size:16px;margin-bottom:4px}
  .zona span{color:var(--suave);font-size:13px}
  input[type=file]{display:none}
  .archivo{margin-top:14px;font-size:14px;color:var(--suave)}
  .archivo b{color:var(--texto)}
  .opciones{margin-top:16px;display:flex;flex-direction:column;gap:9px;font-size:14px}
  label.check{display:flex;gap:9px;align-items:flex-start;cursor:pointer}
  label.check span{color:var(--suave);font-size:13px}
  button{background:var(--acento);color:#fff;border:0;border-radius:8px;padding:11px 20px;
         font-size:15px;font-weight:600;cursor:pointer;margin-top:18px}
  button:disabled{opacity:.5;cursor:not-allowed}
  .estado{display:none;margin-top:4px}
  .estado.visible{display:block}
  .barra{height:6px;background:var(--borde);border-radius:99px;overflow:hidden;margin:14px 0}
  .barra i{display:block;height:100%;width:35%;background:var(--acento);border-radius:99px;
           animation:corre 1.1s ease-in-out infinite}
  @keyframes corre{0%{margin-left:-35%}100%{margin-left:100%}}
  table{width:100%;border-collapse:collapse;margin-top:6px;font-size:14px}
  td{padding:7px 0;border-bottom:1px solid var(--borde)}
  td:last-child{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
  tr:last-child td{border-bottom:0}
  .descargas{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}
  .descargas a{display:inline-block;padding:10px 16px;border:1px solid var(--borde);
               border-radius:8px;text-decoration:none;color:var(--texto);font-size:14px;font-weight:500}
  .descargas a:hover{border-color:var(--acento);color:var(--acento)}
  .descargas a.principal{background:var(--acento);color:#fff;border-color:var(--acento)}
  .aviso{color:var(--aviso)} .malo{color:var(--error)} .bien{color:var(--ok)}
  .problemas{margin-top:16px;font-size:14px}
  .problemas div{display:flex;justify-content:space-between;padding:5px 0;
                 border-bottom:1px solid var(--borde)}
  .pie{color:var(--suave);font-size:13px;margin-top:26px;text-align:center}
  .pie a{color:var(--acento)}
  code{background:rgba(127,127,127,.13);padding:1px 5px;border-radius:4px;font-size:13px}
</style>
</head>
<body>
<div class="envoltura">
  <h1>Procesador de catálogos para Shopify</h1>
  <p class="sub">Sube el Excel del proveedor y descarga el archivo reorganizado, listo para importar.</p>

  <div class="tarjeta">
    <div class="zona" id="zona">
      <strong>Arrastra aquí el Excel del proveedor</strong>
      <span>o haz clic para elegirlo &middot; .xlsx hasta 100 MB</span>
    </div>
    <input type="file" id="archivo" accept=".xlsx,.xlsm,.xls">
    <div class="archivo" id="nombre"></div>

    <div class="opciones">
      <label class="check">
        <input type="checkbox" id="imagenes">
        <span>Comprobar por internet que cada imagen exista (más lento)</span>
      </label>
      <label class="check">
        <input type="file" id="plantilla" accept=".xlsx,.xlsm,.csv" style="display:inline">
        <span>Plantilla de columnas distinta (opcional; si no, se usa la del proyecto)</span>
      </label>
    </div>

    <button id="enviar" disabled>Procesar</button>
  </div>

  <div class="tarjeta estado" id="estado">
    <div id="cabecera"></div>
    <div class="barra" id="barra"><i></i></div>
    <div id="cifras"></div>
    <div class="descargas" id="descargas"></div>
    <div class="problemas" id="problemas"></div>
  </div>

  <p class="pie">Documentación de la API en <a href="/docs">/docs</a></p>
</div>

<script>
const $ = id => document.getElementById(id);
let elegido = null;

$('zona').onclick = () => $('archivo').click();
['dragenter','dragover'].forEach(e => $('zona').addEventListener(e, ev => {
  ev.preventDefault(); $('zona').classList.add('activa');
}));
['dragleave','drop'].forEach(e => $('zona').addEventListener(e, ev => {
  ev.preventDefault(); $('zona').classList.remove('activa');
}));
$('zona').addEventListener('drop', ev => {
  if (ev.dataTransfer.files.length) { $('archivo').files = ev.dataTransfer.files; marcar(); }
});
$('archivo').onchange = marcar;

function marcar(){
  elegido = $('archivo').files[0] || null;
  if (!elegido) return;
  const mb = (elegido.size/1048576).toFixed(1);
  $('nombre').innerHTML = `Seleccionado: <b>${elegido.name}</b> (${mb} MB)`;
  $('enviar').disabled = false;
}

$('enviar').onclick = async () => {
  if (!elegido) return;
  $('enviar').disabled = true;
  $('estado').classList.add('visible');
  $('barra').style.display = 'block';
  $('cabecera').innerHTML = '<strong>Subiendo el archivo...</strong>';
  $('cifras').innerHTML = ''; $('descargas').innerHTML = ''; $('problemas').innerHTML = '';

  const datos = new FormData();
  datos.append('archivo', elegido);
  datos.append('validar_imagenes', $('imagenes').checked ? 'true' : 'false');
  if ($('plantilla').files[0]) datos.append('plantilla', $('plantilla').files[0]);

  let trabajo;
  try {
    const r = await fetch('/api/procesar', {method:'POST', body:datos});
    trabajo = await r.json();
    if (!r.ok) throw new Error(trabajo.detail || 'Error al subir');
  } catch (e) {
    return fallo(e.message);
  }

  $('cabecera').innerHTML = '<strong>Procesando el catálogo...</strong>';
  const reloj = setInterval(async () => {
    const r = await fetch('/api/trabajos/' + trabajo.id);
    const t = await r.json();
    if (t.estado === 'terminado') { clearInterval(reloj); pintar(t); }
    else if (t.estado === 'fallido') { clearInterval(reloj); fallo(t.mensaje); }
  }, 1000);
};

function fallo(mensaje){
  $('barra').style.display = 'none';
  $('cabecera').innerHTML = `<strong class="malo">No se pudo procesar</strong>
     <div style="margin-top:6px;color:var(--suave)">${mensaje}</div>`;
  $('enviar').disabled = false;
}

function pintar(t){
  const s = t.resumen || {};
  $('barra').style.display = 'none';
  $('cabecera').innerHTML = `<strong class="bien">Listo en ${s.segundos}s</strong>`;

  const filas = [
    ['Productos leídos', s.productos_leidos],
    ['Productos exportados', s.productos_exportados],
    ['Con advertencias', s.productos_con_advertencia],
    ['Rechazados por error', s.productos_rechazados],
    ['Variantes exportadas', s.variantes_exportadas],
    ['Imágenes exportadas', s.imagenes_exportadas],
    ['Filas del Excel', s.filas_generadas],
    ['Columnas', s.columnas],
  ];
  $('cifras').innerHTML = '<table>' + filas.map(([k,v]) =>
    `<tr><td>${k}</td><td>${v ?? 0}</td></tr>`).join('') + '</table>';

  const d = t.descargas || {};
  $('descargas').innerHTML =
    (d.csv    ? `<a class="principal" href="${d.csv}">Descargar CSV para Shopify</a>` : '') +
    (d.excel  ? `<a href="${d.excel}">Excel</a>` : '') +
    (d.reporte? `<a href="${d.reporte}">Reporte</a>` : '') +
    (d.zip    ? `<a href="${d.zip}">Todo en ZIP</a>` : '');

  const p = s.problemas || {};
  const claves = Object.keys(p);
  $('problemas').innerHTML = claves.length
    ? '<div style="border:0;padding-top:12px"><b>Detectado durante el proceso</b></div>' +
      claves.map(k => `<div><span>${k.replace(/_/g,' ')}</span><span>${p[k]}</span></div>`).join('')
    : '';
  $('enviar').disabled = false;
}
</script>
</body>
</html>
"""
