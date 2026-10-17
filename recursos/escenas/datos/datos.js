// Ayudas comunes de las escenas de DATOS. Requiere ../base/base.js antes.
const suave = x => x<=0?0:x>=1?1:(x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2);   // entra y sale despacio (para la cámara y el trazo)
const fmt = (v, dec=0) => Number(v).toLocaleString('es-MX',{minimumFractionDigits:dec,maximumFractionDigits:dec});
// tope "bonito" del eje y sus marcas (1, 2, 2.5, 5 x 10^n)
function ejeBonito(max, marcas=4){
  if(max<=0) return {tope:1, paso:.25};
  const bruto = max/marcas, p = Math.pow(10, Math.floor(Math.log10(bruto)));
  const paso = [1,2,2.5,5,10].map(k=>k*p).find(k=>k>=bruto);
  return {tope: paso*Math.ceil(max/paso - 1e-9), paso};
}
// cámara lenta: acercamiento suave de la escena completa (push-in) y un leve giro 3D que se asienta
function empuje(t, T){
  const d = T.camara || 6, k = suave(Math.min(t/d,1));
  const s = 1 + (T.zoom ?? 0.045)*k;
  const el = $('cam'); el.style.transformOrigin = '50% 52%';
  el.style.transform = `perspective(2400px) rotateX(${(1-k)*2.2}deg) scale(${s})`;
}
// firma: por defecto sí; texto según la marca. T.firma=false la quita; un texto la reemplaza.
function firma(T){
  const f = $('firma'); if(!f) return;
  if(T.firma === false){ f.style.display='none'; return; }
  f.style.display='block';
  f.textContent = typeof T.firma === 'string' ? T.firma :
    firmaMarca(T));
  f.style.opacity = prog(t_global, 0, .6);
}
let t_global = 0;
// la tarjeta entra: sube, se enfoca (desenfoque -> nítido) y se asienta con resorte
function entraTarjeta(el, t, a=0.05){
  const r = resorte(t, a, .7), k = prog(t, a, .5);
  el.style.opacity = k;
  el.style.transform = `translateY(${60*(1-r)}px) scale(${.965+.035*r})`;
  el.style.filter = k<1 ? `blur(${(1-k)*10}px)` : 'none';
}
// precarga de las fuentes de las dos marcas: lo que se mide (anchos de globos, tamaño del número) se mide con la letra real
['700 40px Poppins','600 40px Poppins','500 40px Poppins','700 40px Montserrat','400 40px "Open Sans"','400 20px "Roboto Mono"']
  .forEach(f => document.fonts.load(f));
