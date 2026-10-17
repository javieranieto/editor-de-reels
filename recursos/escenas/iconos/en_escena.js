// Pone un ÍCONO ANIMADO del banco dentro de cualquier escena. Va después de ../base/lottie.min.js y ../iconos/iconos.js.
// pintaIcono(el, t, ic, marca): ic = {nombre: "telefono", t: segundo en que arranca, velocidad: 1, loop: false}
// Entra con resorte en su segundo y se reproduce desde ahí; antes de su tiempo no se ve. Determinista (goToAndStop).
const _IC = {};
function pintaIcono(el, t, ic, marca){
  if (!ic || !ic.nombre || !window.ICONOS) { el.style.display = 'none'; return; }
  const d = window.ICONOS[marca || 'ejemplo'][ic.nombre]; if (!d) { el.style.display = 'none'; return; }
  const k = (marca || 'ejemplo') + '/' + ic.nombre;
  if (_IC[el.id] && _IC[el.id].k !== k) { _IC[el.id].a.destroy(); delete _IC[el.id]; }
  if (!_IC[el.id]) { el.innerHTML = ''; _IC[el.id] = {k, a: lottie.loadAnimation({container: el, renderer: 'svg', loop: false, autoplay: false, animationData: d})}; }
  const t0 = ic.t || 0, total = d.op - d.ip;
  let f = Math.max(0, t - t0) * d.fr * (ic.velocidad || 1); f = ic.loop ? f % total : Math.min(f, total - 1);
  _IC[el.id].a.goToAndStop(f, true);
  const r = resorte(t, t0 - 0.05, 0.45);
  el.style.display = t < t0 - 0.05 ? 'none' : 'block';
  el.style.transform = `scale(${0.3 + 0.7 * r})`; el.style.opacity = Math.min(1, r * 1.5);
}
