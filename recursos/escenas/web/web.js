// Piezas comunes de las escenas WEB (buscador, mapa, reseñas) — 14-oct-2026. Se carga DESPUÉS de ../base/base.js.
// El dispositivo depende de la orientación: 16:9 -> ventana de navegador 1560x900; 9:16 -> teléfono 430x900.
// Todo se calcula del segundo t (determinista): nada de setTimeout, requestAnimationFrame ni transiciones CSS.

const eio = x => x<=0?0:x>=1?1:(x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2);   // suave al entrar y al salir (cámara)

// Geometría del dispositivo y de la toma «en reposo» (foco = centro del dispositivo).
function geo(){
  return vertical()
    ? {w:430, h:900, x:325, y:300, s:1.25, cx:540, cy:730}     // teléfono: abajo queda libre la franja de subtítulos
    : {w:1560, h:900, x:180, y:90, s:0.86, cx:960, cy:572};     // navegador: arriba queda la firma
}

// Monta el cromo del dispositivo una sola vez (pestañas y barra de direcciones; isla y barra del teléfono).
function armarDispositivo(){
  const d = $('disp'); if (d.dataset.armado) return; d.dataset.armado = 1;
  const lupa = '<svg class="ic" viewBox="0 0 24 24" style="width:16px;height:16px"><circle cx="10" cy="10" r="6.5" stroke="#5f6368" stroke-width="2.2" fill="none"/><path d="M15 15l5 5" stroke="#5f6368" stroke-width="2.2" stroke-linecap="round"/></svg>';
  d.insertAdjacentHTML('afterbegin', `
    <div class="nav-luces"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>
    <div class="nav-tabs"><div class="nav-tab on"><span class="fav" id="navFav"></span><span class="tt" id="navTit"></span><span class="x">✕</span></div>
      <div class="nav-tab"><span class="fav" style="background:#c9ced6"></span><span class="tt">Nueva pestaña</span><span class="x">✕</span></div>
      <div style="width:30px;height:34px;display:flex;align-items:center;justify-content:center;color:#5f6368;font:20px var(--ui)">+</div></div>
    <div class="nav-barra">
      <svg class="ic" viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7" stroke="#5f6368" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <svg class="ic" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" stroke="#b8bcc2" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <svg class="ic" viewBox="0 0 24 24"><path d="M19 12a7 7 0 1 1-2.05-4.95M19 5v4h-4" stroke="#5f6368" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <div class="nav-omni">${lupa}<span id="navOmni"></span></div>
      <svg class="ic" viewBox="0 0 24 24"><path d="M12 4l2.4 5 5.4.6-4 3.7 1.1 5.4L12 16l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z" stroke="#5f6368" stroke-width="1.8" fill="none" stroke-linejoin="round"/></svg>
      <div class="nav-perfil" style="background:#7b61a8">J</div>
      <svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.8" fill="#5f6368"/><circle cx="12" cy="12" r="1.8" fill="#5f6368"/><circle cx="12" cy="19" r="1.8" fill="#5f6368"/></svg>
    </div>
    <div class="tel-isla"></div>
    <div class="tel-barra" id="telBarra"><span id="telHora">10:24</span><span class="ico">▂▄▆ <span class="tel-bat"></span></span></div>
    <div class="tel-home"></div>`);
  d.insertAdjacentHTML('beforeend', '<div id="brillo"></div>');
  document.body.insertAdjacentHTML('beforeend', '<div id="velo"></div>');
}

// Preparación de cada cuadro: marca, firma, tamaño del dispositivo, textos del cromo.
function montar(T, cromo){
  marca(T); armarDispositivo();
  const f = $('firma');
  if (T.firma === false) f.style.display = 'none';
  else { f.style.display = ''; f.textContent = typeof T.firma === 'string' ? T.firma
         : firmaMarca(T)); }
  const g = geo(), e = $('escena');
  e.style.left = g.x+'px'; e.style.top = g.y+'px'; e.style.width = g.w+'px'; e.style.height = g.h+'px';
  if (cromo){
    $('navTit').textContent = cromo.titulo || ''; $('navOmni').innerHTML = cromo.omni || '<span class="ph">Busca o escribe una dirección</span>';
    $('navFav').style.background = cromo.fav || '#8ab4f8';
    $('telHora').textContent = cromo.hora || '10:24';
    $('telBarra').style.color = cromo.barraClara ? '#fff' : '#111';
  }
  return g;
}

// Posición de un elemento dentro del dispositivo (px sin transformar). Ignora transforms: el desplazamiento
// (scroll) que se haga con translate hay que sumarlo a mano.
function pos(el){
  const d = $('disp'); let x = 0, y = 0, n = el;
  while (n && n !== d){ x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
  return {x, y, w: el.offsetWidth, h: el.offsetHeight, cx: x + el.offsetWidth/2, cy: y + el.offsetHeight/2};
}

// Cámara por puntos clave: [[t, escala, focoX, focoY], ...] (foco en px del dispositivo). Entre puntos, suave.
// Opcional 5.º y 6.º valor: a dónde de la pantalla se lleva el foco (por omisión, el centro de la toma).
function camino(t, puntos){
  const g = geo(); let a = puntos[0], b = puntos[0], k = 0;
  for (let i = 0; i < puntos.length; i++){
    if (t >= puntos[i][0]){ a = puntos[i]; b = puntos[i+1] || puntos[i]; k = b===a ? 0 : eio((t-a[0])/(b[0]-a[0])); }
  }
  const L = (i, def) => { const va = a[i] ?? def, vb = b[i] ?? def; return va + (vb-va)*k; };
  camara($('escena'), L(1,g.s), L(2,g.w/2), L(3,g.h/2), L(4,g.cx), L(5,g.cy), g.x, g.y);
}

// Giro 3D que se asienta (como el teléfono del ejemplo) + golpe opcional en grados.
function girar(t, dur, golpe=0){
  const v = vertical(), k = ease(t/dur);
  const gy = v ? (-10 + 7*k) : (-5 + 3.5*k), gx = v ? (5 - 3*k) : (3 - 2*k);
  $('disp').style.transform = `rotateY(${gy}deg) rotateX(${gx}deg) rotateZ(${golpe}deg)`;
}
function golpeEn(t, a){ return (t>a-0.05 && t<a+0.25) ? Math.sin((t-a)*60)*0.6*(1-(t-a+0.05)/0.3) : 0; }

// Estrellas con relleno parcial (v de 0 a 5). tam en px.
const ESTRELLA = (c, tam) => `<svg width="${tam}" height="${tam}" viewBox="0 0 24 24"><path fill="${c}" d="M12 2.6l2.85 6.05 6.6.78-4.88 4.53 1.3 6.53L12 17.2l-5.87 3.29 1.3-6.53L2.55 9.43l6.6-.78z"/></svg>`;
function estrellas(v, tam=14, vacio='#dadce0'){
  let h = '<span class="estr">';
  for (let i = 0; i < 5; i++){
    const f = Math.max(0, Math.min(1, v - i));
    h += `<span style="position:relative;width:${tam}px;height:${tam}px;display:inline-block">${ESTRELLA(vacio,tam)}
      <span style="position:absolute;left:0;top:0;height:${tam}px;width:${(f*tam).toFixed(1)}px;overflow:hidden">${ESTRELLA('var(--estrella)',tam)}</span></span>`;
  }
  return h + '</span>';
}

// Puntero del ratón (solo navegador). x,y en px del dispositivo; clic de 0 a 1 hace el «apretón» y la onda.
function cursor(x, y, clic=0, visible=1){
  let c = $('cursor');
  if (!c){ $('disp').insertAdjacentHTML('beforeend', `<svg id="cursor" class="cursor" viewBox="0 0 26 34"><path d="M2 2l0 26 7-6.5 4.6 10.2 4.2-1.9-4.5-10 9.7-.3z" fill="#fff" stroke="#111" stroke-width="1.8" stroke-linejoin="round"/></svg><div id="onda" class="toque"></div>`); c = $('cursor'); }
  const ap = clic>0 && clic<1 ? 1 - 0.18*Math.sin(Math.PI*Math.min(1,clic*2.5)) : 1;
  c.style.opacity = visible; c.style.transform = `translate(${x}px,${y}px) scale(${ap})`; c.style.transformOrigin = '2px 2px';
  const o = $('onda'), r = 8 + 34*clic;
  o.style.display = vertical() ? 'none' : ''; o.style.opacity = clic>0 && clic<1 ? 0.5*(1-clic) : 0;
  o.style.left = (x+2-r)+'px'; o.style.top = (y+2-r)+'px'; o.style.width = o.style.height = (2*r)+'px';
}
// Toque en el teléfono: círculo que se expande donde cae el dedo (k de 0 a 1).
function toque(el, x, y, k){
  const r = 14 + 40*k; el.style.display = (k>0 && k<1 && vertical()) ? '' : 'none';
  el.style.left = (x-r)+'px'; el.style.top = (y-r)+'px'; el.style.width = el.style.height = (2*r)+'px'; el.style.opacity = 0.55*(1-k);
}
// Interpola entre dos puntos con suavidad.
const entre = (a, b, k) => a + (b-a)*k;
// Escapa texto que viene de T (los nombres pueden traer & o <).
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
