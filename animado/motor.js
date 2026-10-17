// Motor de animacion "dibujado a mano" sobre canvas.
// Cada video vive en animado/videos/<nombre>/escenas.js y solo describe sus escenas;
// aqui esta todo lo comun: trazos que tiemblan, texto, fondos de papel, camara,
// personajes de pixeles, utileria y el cuadro determinista frame(t).
// Ver animado/LEEME.md.

const cv = document.getElementById('c'), X = cv.getContext('2d');
let W = 1920, H = 1080, S = 1, ALFA = false, DIR = '.';
// Paleta por defecto: neutra, papel y tinta. Cada video pone la de SU marca con
// Object.assign(C, {...}) al principio de su escenas.js (colores sacados del CSS en vivo).
const C = {
  paper: '#F2EDE3', ink: '#1A1917', or: '#E07A4F', orD: '#C25E34', blue: '#5B8FC7',
  green: '#6F8A55', gray: '#A9A69C', light: '#E6E1D5', dark: '#211F1C', white: '#FBF8F2',
  gold: '#E6A93F',
};

// ---------- azar determinista: la linea "hierve" a 12 fps, como animacion a mano ----------
let seed = 1, T = 0;
function rng() {
  seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const r = (a = 1) => (rng() * 2 - 1) * a;
const clamp = (v, a = 0, c = 1) => Math.max(a, Math.min(c, v));
const lerp = (a, c, t) => a + (c - a) * t;
const prog = (t, a, c) => clamp((t - a) / (c - a));
const eo = t => 1 - Math.pow(1 - clamp(t), 3);
const eio = t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const back = t => { t = clamp(t); const c1 = 2.2, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const elastic = t => { t = clamp(t); if (t === 0 || t === 1) return t; return Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 3)) + 1; };
const fmt = n => Math.round(n).toLocaleString('en-US');
const fmt1 = n => n.toFixed(1);

// ---------- primitivas a mano ----------
function line(x1, y1, x2, y2, o = {}) {
  const w = o.w ?? 4, j = o.j ?? 1.8, p = o.passes ?? 2;
  X.strokeStyle = o.c ?? C.ink; X.lineCap = 'round'; X.lineJoin = 'round';
  const len = Math.hypot(x2 - x1, y2 - y1) || 1, nx = -(y2 - y1) / len, ny = (x2 - x1) / len;
  for (let i = 0; i < p; i++) {
    const bow = r(len * 0.01 + j * 0.6);
    X.lineWidth = w * (i ? 0.5 : 1);
    const ax = x1 + r(j), ay = y1 + r(j), bx = x2 + r(j), by = y2 + r(j);
    X.beginPath(); X.moveTo(ax, ay);
    X.quadraticCurveTo((ax + bx) / 2 + nx * bow, (ay + by) / 2 + ny * bow, bx, by); X.stroke();
  }
}
function poly(pts, o = {}) {
  const n = pts.length, cl = o.closed ?? true;
  if (o.fill) {
    const f = o.fj ?? 2.5; X.fillStyle = o.fill; X.beginPath();
    pts.forEach(([x, y], i) => i ? X.lineTo(x + r(f), y + r(f)) : X.moveTo(x + r(f), y + r(f)));
    X.closePath(); X.fill();
  }
  if (o.stroke === false) return;
  for (let i = 0; i < (cl ? n : n - 1); i++) { const a = pts[i], c = pts[(i + 1) % n]; line(a[0], a[1], c[0], c[1], o); }
}
function rect(x, y, w, h, o = {}) { poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], o); }
function blob(cx, cy, rx, ry, o = {}) {           // circulo/elipse temblorosa, trazo que se pasa de largo
  const n = 48, ph1 = rng() * 6.3, ph2 = rng() * 6.3, A = o.wob ?? 0.025;
  const R = a => 1 + A * Math.sin(a * 2 + ph1) + A * 0.6 * Math.sin(a * 3 + ph2);
  if (o.fill) {
    X.fillStyle = o.fill; X.beginPath();
    for (let i = 0; i <= n; i++) { const a = i / n * 6.2832; X.lineTo(cx + Math.cos(a) * rx * R(a) + r(1), cy + Math.sin(a) * ry * R(a) + r(1)); }
    X.fill();
  }
  if (o.stroke === false) return;
  const a0 = rng() * 6.28, turns = o.turns ?? 1.07;
  X.strokeStyle = o.c ?? C.ink; X.lineWidth = o.w ?? 4; X.lineCap = 'round'; X.beginPath();
  for (let i = 0; i <= n * turns; i++) {
    const a = a0 + i / n * 6.2832, k = 1 + (i / n) * 0.025;
    const px = cx + Math.cos(a) * rx * R(a) * k, py = cy + Math.sin(a) * ry * R(a) * k;
    i ? X.lineTo(px, py) : X.moveTo(px, py);
  }
  X.stroke();
}
function hatch(x, y, w, h, o = {}) {              // rayado diagonal recortado a un rectangulo
  X.save(); X.beginPath(); X.rect(x, y, w, h); X.clip();
  const sp = o.sp ?? 18;
  for (let k = -h; k < w; k += sp) line(x + k, y + h, x + k + h, y, { w: o.w ?? 2.5, c: o.c ?? C.ink, j: 1.5, passes: 1 });
  X.restore();
}
function arcHand(cx, cy, rad, a0, a1, o = {}) {
  const n = Math.max(8, Math.ceil(Math.abs(a1 - a0) * 20)), ph = rng() * 6.3;
  X.strokeStyle = o.c ?? C.ink; X.lineWidth = o.w ?? 4; X.lineCap = 'round'; X.beginPath();
  for (let i = 0; i <= n; i++) {
    const a = a0 + (a1 - a0) * i / n, rr = rad * (1 + 0.012 * Math.sin(a * 3 + ph));
    i ? X.lineTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr) : X.moveTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr);
  }
  X.stroke();
}
function txt(s, x, y, o = {}) {
  const size = o.size ?? 80;
  X.save(); X.translate(x + r(o.j ?? 0.6), y + r(o.j ?? 0.6)); X.rotate((o.rot ?? 0) + r(o.jr ?? 0.002));
  if (o.scale) X.scale(o.scale, o.scale);
  X.font = `${o.it ? 'italic ' : ''}${o.wt ?? 500} ${size}px ${o.f ?? 'SSerif'}`;
  X.letterSpacing = (o.ls ?? 0) + 'px'; X.textAlign = o.al ?? 'center'; X.textBaseline = o.bl ?? 'alphabetic';
  X.globalAlpha = o.a ?? 1;
  if (o.reveal !== undefined) {
    const w = X.measureText(s).width, x0 = X.textAlign === 'center' ? -w / 2 : X.textAlign === 'right' ? -w : 0;
    X.beginPath(); X.rect(x0 - 30, -size * 1.4, (w + 60) * clamp(o.reveal), size * 2.2); X.clip();
  }
  if (o.stroke) { X.lineWidth = o.stroke; X.strokeStyle = o.sc ?? C.ink; X.lineJoin = 'round'; X.strokeText(s, 0, 0); }
  X.fillStyle = o.c ?? C.ink; X.fillText(s, 0, 0); X.restore();
}
function tw(s, size, wt = 500, f = 'SSerif', ls = 0) {
  X.save(); X.font = `${wt} ${size}px ${f}`; X.letterSpacing = ls + 'px'; const w = X.measureText(s).width; X.restore(); return w;
}
function swoosh(x1, x2, y, p, o = {}) {           // subrayado de plumon naranja que se pinta
  if (p <= 0) return; const xe = lerp(x1, x2, eo(p));
  line(x1, y, xe, y - 8, { w: o.w ?? 16, c: o.c ?? C.or, j: 2, passes: 1 });
  if (p > 0.4) line(x1 + 30, y + 16, lerp(x1 + 30, x2 - 20, eo((p - 0.4) / 0.6)), y + 10, { w: (o.w ?? 16) * 0.6, c: o.c ?? C.or, j: 2, passes: 1 });
}
function arrow(x1, y1, x2, y2, o = {}) {
  line(x1, y1, x2, y2, o); const a = Math.atan2(y2 - y1, x2 - x1), L = o.head ?? 26;
  line(x2, y2, x2 - Math.cos(a - 0.5) * L, y2 - Math.sin(a - 0.5) * L, o);
  line(x2, y2, x2 - Math.cos(a + 0.5) * L, y2 - Math.sin(a + 0.5) * L, o);
}

// ---------- fondos (textura fija: comprime bien) ----------
function makeTex(base, spot, fib) {
  const c = document.createElement('canvas'); c.width = cv.width; c.height = cv.height;
  const g = c.getContext('2d'); g.fillStyle = base; g.fillRect(0, 0, c.width, c.height);
  const keep = seed; seed = 4242;
  for (let i = 0; i < 26000; i++) { g.fillStyle = spot[i % spot.length]; g.fillRect(rng() * c.width, rng() * c.height, 1 + rng() * 1.6, 1 + rng() * 1.6); }
  g.strokeStyle = fib; g.lineWidth = 1;
  for (let i = 0; i < 900; i++) {
    const x = rng() * c.width, y = rng() * c.height, a = rng() * 6.3, L = 6 + rng() * 22;
    g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a) * L * .5 + rng() * 4, y + Math.sin(a) * L * .5, x + Math.cos(a) * L, y + Math.sin(a) * L); g.stroke();
  }
  const v = g.createRadialGradient(c.width / 2, c.height / 2, c.height * 0.45, c.width / 2, c.height / 2, c.width * 0.72);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(60,40,20,0.13)'); g.fillStyle = v; g.fillRect(0, 0, c.width, c.height);
  seed = keep; return c;
}
let TEX = {};
function bg(k) { if (ALFA) return; X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(TEX[k], 0, 0); X.restore(); }
function cam(z = 1, px = 0, py = 0, rot = 0, shake = 0) {
  const sx = shake * Math.sin(T * 91.7), sy = shake * Math.cos(T * 73.3);
  X.translate(W / 2 + px + sx, H / 2 + py + sy); X.rotate(rot); X.scale(z, z); X.translate(-W / 2, -H / 2);
}
const punch = (lt, k = 0.14, d = 0.32) => 1 + k * (1 - eo(lt / d));
const shakeAt = (lt, t0, amp = 14, d = 0.35) => lt < t0 ? 0 : amp * Math.max(0, 1 - (lt - t0) / d);


// ---------- personajes de pixeles ----------
// g: filas de caracteres ('.' = vacio); col: color por caracter; by = la base (los pies).
// aspecto 2 = pixel el doble de alto que de ancho, como los bloques de una terminal.
function sprite(g, col, cx, by, px, o = {}) {
  if (typeof g[0] === 'string') g = g.map(s => s.split(''));
  const rows = g.length, cols = g[0].length;
  X.save(); X.translate(cx, by); X.rotate(o.rot || 0);
  const sq = o.sq ?? 1; X.scale((o.flip ? -1 : 1) / Math.sqrt(sq), sq);
  if (o.shadow !== false) { X.fillStyle = 'rgba(20,20,19,0.13)'; X.beginPath(); X.ellipse(0, px * 0.25, px * (cols / 2 - 1), px * 0.8, 0, 0, 6.3); X.fill(); }
  const ph = px * (o.aspecto ?? 1), ox = -(cols / 2) * px, oy = -rows * ph;
  const filled = (rr, c) => rr >= 0 && rr < rows && c >= 0 && c < cols && g[rr][c] !== '.';
  for (let rr = 0; rr < rows; rr++) for (let c = 0; c < cols; c++) {
    const ch = g[rr][c]; if (ch === '.') continue;
    X.fillStyle = col[ch]; X.fillRect(ox + c * px - 0.6 + r(px * 0.03), oy + rr * ph - 0.6 + r(px * 0.03), px + 1.2, ph + 1.2);
  }
  const lw = Math.max(2, px * 0.13), lj = px * 0.05;
  for (let rr = 0; rr < rows; rr++) for (let c = 0; c < cols; c++) {
    if (!filled(rr, c)) continue; const x = ox + c * px, y = oy + rr * ph;
    if (!filled(rr - 1, c)) line(x, y, x + px, y, { w: lw, j: lj, passes: 1 });
    if (!filled(rr + 1, c)) line(x, y + ph, x + px, y + ph, { w: lw, j: lj, passes: 1 });
    if (!filled(rr, c - 1)) line(x, y, x, y + ph, { w: lw, j: lj, passes: 1 });
    if (!filled(rr, c + 1)) line(x + px, y, x + px, y + ph, { w: lw, j: lj, passes: 1 });
  }
  X.restore();
}
const blinkAt = t => (t % 2.3) < 0.1;                 // parpadeo cada 2.3 s
const wave = t => (Math.floor(t * 7) % 2) ? 'mid' : 'up';
const walk = (t, f = 8) => Math.floor(t * f) % 2;

// ---------- utileria dibujada ----------
function coin(x, y, rad) { blob(x, y, rad, rad, { fill: C.gold, w: 4 }); txt('$', x, y + rad * 0.38, { size: rad * 1.1, wt: 800, f: 'Inter' }); }
function bug(x, y, s, dead) {
  X.save(); X.translate(x, y); X.scale(s, s);
  for (let i = -1; i <= 1; i++) { line(-4, i * 6, -18, i * 9 + 4, { w: 2.5, passes: 1 }); line(4, i * 6, 18, i * 9 + 4, { w: 2.5, passes: 1 }); }
  line(-4, -10, -10, -20, { w: 2, passes: 1 }); line(4, -10, 10, -20, { w: 2, passes: 1 });
  blob(0, 0, 9, 13, { fill: C.ink, w: 2 });
  X.restore();
  if (dead > 0) {
    blob(x, y, 34 * s, 34 * s, { c: C.or, w: 6, turns: eo(dead) * 1.07 });
    if (dead > 0.5) { line(x - 22 * s, y - 22 * s, x + 22 * s, y + 22 * s, { c: C.or, w: 6 }); line(x + 22 * s, y - 22 * s, x - 22 * s, y + 22 * s, { c: C.or, w: 6 }); }
  }
}
function briefcase(x, y, s) {
  X.save(); X.translate(x, y); X.scale(s, s);
  blob(0, -92, 34, 22, { w: 7, turns: 0.55 });
  rect(-70, -80, 140, 80, { fill: '#8A5A3C', w: 5 }); line(-70, -52, 70, -52, { w: 4 }); rect(-10, -60, 20, 16, { fill: C.gold, w: 3 });
  X.restore();
}
function trophy(x, y, s) {
  X.save(); X.translate(x, y); X.scale(s, s);
  blob(-38, -62, 16, 18, { w: 5, turns: 1 }); blob(38, -62, 16, 18, { w: 5, turns: 1 });
  poly([[-40, -90], [40, -90], [28, -30], [-28, -30]], { fill: C.gold, w: 5 });
  rect(-8, -30, 16, 22, { fill: C.gold, w: 4 }); rect(-30, -8, 60, 14, { fill: C.ink, w: 3 });
  txt('1', 0, -48, { size: 34, wt: 800, f: 'Inter' });
  X.restore();
}
function cursorShape(x, y, s) {
  const p = [[0, 0], [0, 34], [9, 26], [15, 40], [21, 37], [15, 24], [26, 24]].map(([a, c]) => [x + a * s, y + c * s]);
  poly(p, { fill: C.white, w: 5 });
}
const CODE = (() => { const k = seed; seed = 777; const L = []; for (let i = 0; i < 80; i++) L.push({ ind: Math.floor(rng() * 4), w: 120 + rng() * 520, c: [C.or, C.blue, C.green, C.light, C.light, C.gray][Math.floor(rng() * 6)], w2: rng() < .5 ? 60 + rng() * 200 : 0 }); seed = k; return L; })();
function codeLines(x, y, w, h, off, sc = 1, dark = true) {
  X.save(); X.beginPath(); X.rect(x, y, w, h); X.clip();
  const lh = 38 * sc, first = Math.floor(off / lh);
  for (let i = first; i < first + h / lh + 2; i++) {
    const L = CODE[((i % CODE.length) + CODE.length) % CODE.length], yy = y + i * lh - off + 20;
    const x0 = x + 40 + L.ind * 40 * sc;
    line(x0, yy, x0 + L.w * sc, yy, { w: 12 * sc, c: dark ? L.c : (L.c === C.light ? C.gray : L.c), j: 1, passes: 1 });
    if (L.w2) line(x0 + L.w * sc + 24, yy, x0 + L.w * sc + 24 + L.w2 * sc, yy, { w: 12 * sc, c: dark ? C.gray : C.light, j: 1, passes: 1 });
  }
  X.restore();
}
function streaks(t, n, c, y0 = 0, y1 = H, spd = 3200, len = 260) {
  const k = seed; seed = 99;
  for (let i = 0; i < n; i++) {
    const yy = y0 + rng() * (y1 - y0), off = rng() * (W + 600), sp = spd * (0.6 + rng() * 0.8);
    const xx = W + 300 - ((off + t * sp) % (W + 600));
    seed = k + i; line(xx, yy, xx + len * (0.5 + (i % 3) * 0.3), yy, { w: 4, c, passes: 1, j: 1 }); seed = 99 + i * 7;
  }
  seed = k;
}
function header(s, c) { txt(s, 120, 118, { f: 'Pix', size: 44, al: 'left', c, ls: 2, wt: 700 }); }


// ---------- configuracion, escenas y cuadro ----------
let VIDEO = { lienzo: [1920, 1080], salida: [2560, 1440], dur: 10, fps: 24, fuentes: {}, fondos: {} };
function configurar(o) {
  Object.assign(VIDEO, o); [W, H] = VIDEO.lienzo;
  cv.width = VIDEO.salida[0]; cv.height = VIDEO.salida[1]; S = cv.width / W;
}
const SC = [];
function escena(a, b, fn) { SC.push({ a, b, fn }); }
function longitudTrazo(d) {                          // largo de un trazo SVG, para dibujarlo "a mano"
  const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg'), p = document.createElementNS(ns, 'path');
  svg.setAttribute('style', 'position:absolute;width:0;height:0'); p.setAttribute('d', d);
  svg.appendChild(p); document.body.appendChild(svg); return p.getTotalLength();
}
async function imagen(src) {                        // un logo o asset REAL del video (ruta relativa a animado/)
  const im = new Image(); im.src = src;
  try { await im.decode(); } catch (e) { throw new Error('no se pudo cargar la imagen ' + src); }
  return im;
}

function frame(t) {
  T = t; seed = Math.floor(t * 12) * 7919 + 13;     // la linea "hierve" a 12 fps
  // Se limpia SIEMPRE, no solo con --alfa: un video sin bg() dibujaria cada cuadro encima
  // del anterior, y entonces frame(t) dependeria del orden en que se piden los cuadros.
  X.setTransform(1, 0, 0, 1, 0, 0); X.clearRect(0, 0, cv.width, cv.height);
  X.setTransform(S, 0, 0, S, 0, 0);
  const s = SC.find(q => t >= q.a && t < q.b) || SC[SC.length - 1];
  s.fn(t - s.a, s.b - s.a);
  if (VIDEO.encima) VIDEO.encima(t);
}

function cargar(src) {
  return new Promise((ok, mal) => {
    const s = document.createElement('script'); s.src = src; s.onload = ok;
    s.onerror = () => mal(new Error('no se pudo cargar ' + src)); document.body.appendChild(s);
  });
}
async function init() {
  const q = new URLSearchParams(location.search);
  DIR = q.get('v') || '.'; ALFA = q.has('alfa');
  await cargar(DIR + '/escenas.js');
  for (const [fam, [archivo, desc]] of Object.entries(VIDEO.fuentes)) {
    const f = new FontFace(fam, `url(${archivo})`, desc || {});
    try { await f.load(); } catch (e) { throw new Error(`no se pudo cargar la fuente ${fam} (${archivo}): la ruta es relativa a animado/`); }
    document.fonts.add(f);
  }
  await document.fonts.ready;
  for (const [k, f] of Object.entries(VIDEO.fondos)) TEX[k] = makeTex(f.base, f.manchas, f.fibras);
  if (VIDEO.preparar) await VIDEO.preparar();
  window.READY = true;
  if (!q.has('render')) {                           // vista previa en vivo, en bucle
    const t0 = performance.now() - (parseFloat(q.get('t') || 0) * 1000);
    const loop = () => { frame(((performance.now() - t0) / 1000) % VIDEO.dur); requestAnimationFrame(loop); }; loop();
  }
}
init().catch(e => { window.ERROR = String(e); console.error(e); });
