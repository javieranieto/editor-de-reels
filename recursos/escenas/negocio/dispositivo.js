// Ayudas compartidas de las escenas de NEGOCIO (14-oct-2026). Va DESPUÉS de ../base/base.js.
// - montaDispositivo(tipo): arma laptop (16:9) o tablet/teléfono (9:16) dentro de #escena y devuelve #app.
// - camaraNeg(t, claves): cámara que se acerca a un elemento del software; en vertical NUNCA invade la franja
//   de subtítulos (70%-82% del alto): si el acercamiento la tocaría, sube el dispositivo.
// - cursorNeg(t, puntos): flecha de ratón (laptop) o toque con onda (tablet/teléfono) en coordenadas del software.
// - pesos(n): $27,300.   Todo determinista: se calcula de t, sin temporizadores ni transiciones.

const pesos = (n, dec=0) => (n<0?'-':'') + '$' + Math.abs(Number(n)).toLocaleString('es-MX',{minimumFractionDigits:dec,maximumFractionDigits:dec});
const lerp = (a,b,k) => a + (b-a)*k;
const lim = (x,a=0,b=1) => Math.max(a, Math.min(b, x));

// Medidas de cada dispositivo (px del dispositivo) y dónde va el software dentro.
const DISPOSITIVOS = {
  laptop:   {w:1480, h:878,  app:{x:100, y:26, w:1280, h:800}},
  tablet:   {w:808,  h:1108, app:{x:24,  y:24, w:760,  h:1060}},
  telefono: {w:430,  h:900,  app:{x:14,  y:14, w:402,  h:872}},
};
// Encuadre base: escala y centro en pantalla. En vertical el dispositivo termina antes del 70% del alto (1344 px).
const ENCUADRE = {
  laptop:   {s:0.97, cx:960, cy:560, foco:540},
  tablet:   {s:1.04, cx:540, cy:760, foco:640},
  telefono: {s:1.30, cx:540, cy:742, foco:640},
};
const LIMITE_V = 1330;   // borde inferior máximo del dispositivo en vertical (la franja libre empieza en 1344)
let DISP = null, TIPO = null;

function montaDispositivo(tipo, horaTel){
  TIPO = tipo; DISP = DISPOSITIVOS[tipo];
  const esc = $('escena');
  if (!$('ventana')){ const v = document.createElement('div'); v.id = 'ventana'; esc.parentNode.insertBefore(v, esc); v.appendChild(esc); }
  esc.className = tipo; esc.style.width = DISP.w + 'px'; esc.style.height = DISP.h + 'px';
  const piso = tipo==='laptop' ? `<div id="piso" style="left:60px;top:840px;width:1360px;height:90px"></div>` : '';
  esc.innerHTML = piso + `<div id="disp" style="width:${DISP.w}px;height:${DISP.h}px"><div id="tapa"></div>
    ${tipo==='laptop' ? '<div id="camarita"></div><div id="base"></div>' : ''}
    <div id="pantalla"><div id="app"></div>${tipo==='telefono' ? '<div id="isla"></div>' : ''}</div><div id="brillo"></div></div>`;
  return $('app');
}

// posición de un elemento en coordenadas del dispositivo (los offsets no los mueven las transformaciones)
function posEn(el){
  let x=0, y=0, e=el; const raiz=$('escena');
  while (e && e!==raiz){ x+=e.offsetLeft; y+=e.offsetTop; e=e.offsetParent; }
  return {x, y, w:el.offsetWidth, h:el.offsetHeight, cx:x+el.offsetWidth/2, cy:y+el.offsetHeight/2};
}
// lo mismo pero relativo al software (#app), para cursor, recuadros y avisos que viven dentro
function posApp(el){ const p=posEn(el); p.x-=DISP.app.x; p.y-=DISP.app.y; p.cx-=DISP.app.x; p.cy-=DISP.app.y; return p; }

// claves: [{t, foco: elemento | id | null (todo), z: acercamiento (1 = encuadre), d: duración del movimiento, dx, dy}]
function camaraNeg(t, claves){
  const E = ENCUADRE[TIPO], W = window.innerWidth;
  let c = {fx:DISP.w/2, fy:DISP.h/2, sx:E.cx, sy:E.cy, z:1};
  for (const k of claves){
    const p = prog(t, k.t, k.d || 0.9); if (p<=0) continue;
    const el = typeof k.foco==='string' ? $(k.foco) : k.foco;
    const f = el ? posEn(el) : {cx:DISP.w/2, cy:DISP.h/2};
    const zf = k.z || 1;
    const obj = el ? {fx:f.cx+(k.dx||0), fy:f.cy+(k.dy||0), sx:W/2, sy:E.foco, z:zf} : {fx:DISP.w/2, fy:DISP.h/2, sx:E.cx, sy:E.cy, z:zf};
    c = {fx:lerp(c.fx,obj.fx,p), fy:lerp(c.fy,obj.fy,p), sx:lerp(c.sx,obj.sx,p), sy:lerp(c.sy,obj.sy,p), z:lerp(c.z,obj.z,p)};
  }
  const z = c.z * (1 + 0.025*ease(t/7));          // respiración lenta: nunca está quieta
  const s = E.s * z;
  let sy = c.sy;
  let sx = c.sx;
  // si el software ya es más ancho (o alto) que el cuadro, que no se vea el fondo de un lado: se recorre poco a poco
  const H = window.innerHeight, m = 24, A = DISP.app;
  const gw = lim((A.w*s - (W-2*m))/220);
  if (gw > 0){ const izq = sx + (A.x - c.fx)*s, der = izq + A.w*s;
    if (izq > m) sx -= (izq - m)*gw; else if (der < W-m) sx += ((W-m) - der)*gw; }
  if (!vertical()){ const gh = lim((A.h*s - (H-2*m))/220);
    if (gh > 0){ const arr = sy + (A.y - c.fy)*s, aba = arr + A.h*s;
      if (arr > m) sy -= (arr - m)*gh; else if (aba < H-m) sy += ((H-m) - aba)*gh; } }
  if (vertical()){
    // en 9:16 el dispositivo no se sale de lado: si cabe a lo ancho, va centrado; si no, sus bordes tapan el cuadro
    const dw = DISP.w*s;
    if (dw <= W) sx = W/2 + (c.fx - DISP.w/2)*s;
    else { const izq = sx - c.fx*s, der = izq + dw; if (izq > 0) sx -= izq; else if (der < W) sx += W - der; }
  }
  const ven = $('ventana');
  if (vertical()){
    // si sobra espacio abajo, el foco baja (hasta 1120) para no dejar hueco; si el dispositivo pasa de LIMITE_V,
    // se desvanece antes de la franja de subtítulos (máscara), así la franja queda libre a cualquier acercamiento
    const L = LIMITE_V - (DISP.h - c.fy)*s;
    sy = Math.max(sy, Math.min(1120, L));
    const fondo = sy + (DISP.h - c.fy)*s, k = lim((fondo - LIMITE_V)/120);
    const B = LIMITE_V + 6, A = B - 170*k;
    ven.style.webkitMaskImage = ven.style.maskImage = `linear-gradient(to bottom, #000 0px, #000 ${A}px, transparent ${B}px)`;
  } else { ven.style.webkitMaskImage = ven.style.maskImage = 'none'; }
  camara($('escena'), s, c.fx, c.fy, sx, sy);
  // giro 3D: se nota en el plano abierto y se endereza al acercarse (lo importante se lee de frente)
  const plano = 1 - lim((c.z-1)/0.45);
  const gy = (TIPO==='laptop' ? -9 : -10) + 5*ease(t/8), gx = (TIPO==='laptop' ? 5 : 4) - 2*ease(t/8);
  $('disp').style.transform = `rotateY(${gy*(0.25+0.75*plano)}deg) rotateX(${gx*(0.25+0.75*plano)}deg)`;
  return c.z;
}

// puntos: [{t, el | x,y (coord. del software), clic:true}] — el cursor viaja entre puntos y hace clic al llegar
function cursorNeg(t, puntos){
  const app = $('app');
  let cur = $('cursor'), onda = $('onda');
  if (!cur){
    app.insertAdjacentHTML('beforeend', `<svg id="cursor" viewBox="0 0 24 24"><path d="M3 2l17 10.2-7.4 1.6-3.4 7L3 2z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg><div id="onda"></div>`);
    cur = $('cursor'); onda = $('onda');
  }
  const tactil = TIPO !== 'laptop';
  if (!puntos || !puntos.length){ cur.style.opacity = 0; onda.style.opacity = 0; return; }
  const P = puntos.map(p => { const e = typeof p.el==='string' ? $(p.el) : p.el; if (e){ const q=posApp(e); return {t:p.t, x:q.x+(p.ox!=null?p.ox:q.w*0.55), y:q.y+(p.oy!=null?p.oy:q.h*0.6), clic:p.clic}; } return p; });
  let x = P[0].x + 140, y = P[0].y + 160;               // entra desde abajo a la derecha
  for (const p of P){ const k = prog(t, p.t - 0.7, 0.7); x = lerp(x, p.x, k); y = lerp(y, p.y, k); }
  const vis = lim((t - (P[0].t - 0.9))/0.25) * (1 - lim((t - (P[P.length-1].t + 0.9))/0.3));
  let pulso = 1, oo = 0, os = 0.3;
  for (const p of P){ if (!p.clic) continue; const d = t - p.t; if (d>=-0.08 && d<0.12) pulso = 0.82; if (d>=0 && d<0.5){ oo = 1 - d/0.5; os = 0.3 + 1.4*d/0.5; } }
  cur.style.opacity = tactil ? 0 : vis;
  cur.style.transform = `translate(${x}px,${y}px) scale(${pulso})`;
  onda.style.opacity = oo; onda.style.left = x + 'px'; onda.style.top = y + 'px'; onda.style.transform = `scale(${os})`;
  if (tactil){ onda.style.background = 'color-mix(in srgb,var(--acento) 25%,transparent)'; }
}

// firma de marca (o nada si T.firma === false)
function firmaNeg(T){
  const f = $('firma'); if (!f) return;
  if (T.firma === false){ f.style.display = 'none'; return; }
  f.style.display = '';
  f.textContent = firmaMarca(T);
}
// iconos de línea para la barra lateral (genéricos)
const ICO = {
  inicio:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  agenda:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  clientes:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6M16 4a4 4 0 0 1 0 8M22 21c0-3-2-5-4-5.5"/></svg>',
  cotiz:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h8M9 17h6"/></svg>',
  grafica:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  ajustes:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
  mensajes:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 4V5a1 1 0 0 1 1-1z"/></svg>',
  megafono:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 10v4h4l6 5V5L7 10zM16 8a5 5 0 0 1 0 8M19 5a9 9 0 0 1 0 14"/></svg>',
  busca:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/></svg>',
  campana:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 16V11a6 6 0 0 0-12 0v5l-2 2h16zM10 21h4"/></svg>',
  mas:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 5v14M5 12h14"/></svg>',
};
const ICONO = (n, tam=18) => ICO[n].replace('<svg ', `<svg width="${tam}" height="${tam}" `);
// barra lateral del software de escritorio
function ladoNeg(T, activo, items){
  const ini = (T.negocio||'').split(/\s+/).filter(w=>w.length>2).slice(0,2).map(w=>w[0]).join('').toUpperCase();
  return `<div class="lado"><div class="negocio"><div class="logo-neg">${ini}</div><div><b>${T.negocio}</b><small>${T.sucursal||'Sucursal Centro'}</small></div></div>
    ${items.map(([ic,n,c])=>`<div class="nav ${n===activo?'on':''}">${ICONO(ic)}${n}${c?`<span class="cnt">${c}</span>`:''}</div>`).join('')}
    <div class="usuario"><div class="ini">${(T.usuario||'Recepción').slice(0,2).toUpperCase()}</div><div>${T.usuario||'Recepción'}<small>En línea</small></div></div></div>`;
}
function arribaNeg(texto){
  return `<div class="arriba"><div class="busca">${ICONO('busca',16)}${texto}</div>
    <div class="der"><span>Hoy</span><div class="campana">${ICONO('campana',20)}<i></i></div><div class="ava" style="background:#5c6b8a">AD</div></div></div>`;
}
// colores de avatar por nombre (estable)
const COLORES_AVA = ['#5b7bd5','#d0805a','#4fa37a','#9b6bc9','#c9a23f','#d06a8f','#4a9bb5','#7d8aa5'];
const colorAva = s => COLORES_AVA[[...s].reduce((a,c)=>a+c.charCodeAt(0),0) % COLORES_AVA.length];
const iniciales = s => s.split(/\s+/).slice(0,2).map(w=>w[0]).join('').toUpperCase();
