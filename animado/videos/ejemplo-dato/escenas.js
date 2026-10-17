// Ejemplo minimo: un DATO dibujado a mano, con fondo transparente, para poner encima
// de un reel en CapCut (una cifra que se encierra en un circulo). 3 s, vertical 1080x1920.
//   python animado/render.py ejemplo-dato --fotos 0.3 1.2 2.8 --alfa   -> hoja.png para revisar
//   python animado/render.py ejemplo-dato --alfa                       -> .mov qtrle/argb
// Sin bg(): lo que no se dibuja queda transparente.
// El negocio es el demo ficticio (Servicios Alcaraz, electricista a domicilio). Un dato REAL
// lleva aqui su fuente primaria: URL y fecha en que se comprobo.

configurar({
  lienzo: [1080, 1920], salida: [1080, 1920], dur: 3, fps: 30,
  fuentes: {
    SSerif: ['fuentes/SourceSerif4.ttf', { weight: '200 900' }],
    Inter: ['fuentes/Inter.ttf', { weight: '100 900' }],
    Hand: ['fuentes/Caveat-Bold.ttf'],
  },
});

escena(0, 3, lt => {
  const sale = prog(lt, 2.6, 3.0);                   // se va encogiendo al final
  X.save(); X.translate(540, 520); X.scale(1 - eo(sale), 1 - eo(sale)); X.translate(-540, -520);
  const p = back(prog(lt, 0.05, 0.35));
  if (p > 0) {
    X.save(); X.translate(540, 520); X.rotate(-0.04); X.scale(p, p);
    rect(-330, -170, 660, 340, { fill: C.white, w: 7 });
    txt('24/7', 0, 60, { size: 190, wt: 700, c: C.or });
    X.restore();
  }
  if (lt > 0.4) blob(540, 470, 300, 150, { c: C.ink, w: 9, turns: eo(prog(lt, 0.4, 0.8)) * 1.07 });
  txt('urgencias eléctricas', 540, 780, { f: 'Hand', size: 76, c: C.white, stroke: 10, reveal: prog(lt, 0.7, 1.3) });
  X.restore();
});
