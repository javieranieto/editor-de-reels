// Base común del banco de escenas. Cada escena: <script src="../base/base.js"></script> y define render(t, T, escena).
// Ayudas: ease/prog/resorte, cont(n) para números, camara(el, s, px, py, cx, cy), marca(T), orient().
const ease = x => x<=0?0:x>=1?1:1-Math.pow(1-x,3);
const prog = (t,a,d) => ease((t-a)/d);
const resorte = (t,a,d=0.45) => { const x=(t-a)/d; if(x<=0) return 0; if(x>=1) return 1; const c=1.70158*1.2, y=x-1; return 1+(c+1)*y*y*y+c*y*y; };
const $ = id => document.getElementById(id);
const vertical = () => window.innerHeight > window.innerWidth;
// Las marcas llegan en window.MARCAS = {id: {colores, letras, firma, archivos_de_letra}} (las pone capturar.py
// desde recursos/marcas/*.json). T.marca es el id; sin T.marca se usa "ejemplo".
function marcaDe(T){ const M = window.MARCAS || {}; return M[(T && T.marca) || 'ejemplo'] || M.ejemplo || {}; }
function marca(T){ const m = marcaDe(T), st = document.body.style;
  for (const [k, v] of Object.entries(m.colores || {})) st.setProperty('--' + k, v);
  const L = m.letras || {}; if (L.titulos) st.setProperty('--titulos', `"${L.titulos}",sans-serif`);
  if (L.cuerpo) st.setProperty('--cuerpo', `"${L.cuerpo}",sans-serif`); if (L.mono) st.setProperty('--mono', `"${L.mono}",monospace`);
  for (const [fam, arch] of Object.entries(m.archivos_de_letra || {})) if (!document.fonts.check(`16px "${fam}"`)) {
    const f = new FontFace(fam, `url("../../fuentes/${arch}")`); document.fonts.add(f); f.load(); }
  document.body.classList.toggle('vertical', vertical()); document.body.classList.toggle('horizontal', !vertical()); }
function firmaMarca(T){ return marcaDe(T).firma || ''; }
// número que sube hasta su valor; dec = decimales; pre/suf = "$", "%", "x"
function cont(v, p, dec=0, pre="", suf=""){ const x=v*p; return pre + x.toLocaleString('es-MX',{minimumFractionDigits:dec,maximumFractionDigits:dec}) + suf; }
// cámara: escala s alrededor del punto (px,py) del elemento y lo lleva al punto (cx,cy) de la pantalla
function camara(el, s, px, py, cx, cy, ox=0, oy=0){
  el.style.transformOrigin = `${px}px ${py}px`;
  el.style.transform = `translate(${cx-(ox+px)}px, ${cy-(oy+py)}px) scale(${s})`;
}
// entrada estándar de un elemento: sube 30px y aparece
function entra(el, t, a, d=0.35, dy=30){ const k=prog(t,a,d); el.style.opacity=k; el.style.transform=`translateY(${dy*(1-k)}px)`; return k; }
