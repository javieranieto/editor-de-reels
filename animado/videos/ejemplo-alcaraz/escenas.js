// Ejemplo completo y corto: dos escenas de 16:9 con fondos de papel, camara, un personaje
// de pixeles y un pie fijo. Es la estructura que se copia para un video nuevo.
//   python animado/render.py ejemplo-alcaraz --fotos 0.4 1.5 2.9 3.4 4.5 5.9   -> hoja.png
//   python animado/render.py ejemplo-alcaraz                                   -> MP4 (mudo: no hay audio.json)
// El negocio es el demo ficticio: Servicios Alcaraz, electricista a domicilio en Guadalajara.
// No hay cifras: un dato real llevaria aqui su fuente primaria (URL y fecha).

// La paleta de la marca va primero (en un negocio real: los colores de su CSS en vivo).
Object.assign(C, { or: '#E07A4F', gold: '#F2B33D' });

configurar({
  lienzo: [1920, 1080], salida: [1920, 1080], dur: 6, fps: 24,
  fuentes: {
    SSerif: ['fuentes/SourceSerif4.ttf', { weight: '200 900' }],
    Inter: ['fuentes/Inter.ttf', { weight: '100 900' }],
    Hand: ['fuentes/Caveat-Bold.ttf'],
    Pix: ['fuentes/SilkscreenBold.ttf'],
  },
  fondos: {
    paper: { base: C.paper, manchas: ['rgba(120,100,70,0.10)', 'rgba(255,255,255,0.35)', 'rgba(90,70,50,0.06)'], fibras: 'rgba(120,100,70,0.08)' },
    dark: { base: C.dark, manchas: ['rgba(255,255,255,0.05)', 'rgba(0,0,0,0.25)'], fibras: 'rgba(255,255,255,0.03)' },
  },
});

// Los cortes se declaran por tiempos. Con musica, salen de su rejilla de beats
// (pipeline/musica.py: analizar + rejilla), no a ojo.
const CUT = [0, 3, 6];

// Un foco de pixeles: cada letra es un color, '.' es vacio. Pixel cuadrado (aspecto 1);
// un personaje que imita los bloques de una terminal lleva { aspecto: 2 }.
const FOCO = ['...YYY...', '..YYYYY..', '.YYWYYYY.', '.YYYYYYY.', '.YYYYYYY.', '..YYYYY..', '...GGG...', '...GGG...', '....G....'];

// ---------- 1. La pregunta (fondo claro) ----------
escena(CUT[0], CUT[1], lt => {
  bg('paper');
  X.save(); cam(punch(lt));
  txt('¿Se fue la luz?', 760, 470, { size: 120, wt: 700, reveal: prog(lt, 0.1, 0.7) });
  swoosh(380, 1140, 525, prog(lt, 0.6, 1.1));
  txt('llama, no te arriesgues', 760, 660, { f: 'Hand', size: 72, c: C.orD, reveal: prog(lt, 1.1, 1.7) });
  const prendido = lt > 1.4;
  const cy = 820 - FOCO.length * 26 / 2;
  if (prendido) for (let i = 0; i < 8; i++) {          // rayos: el foco se enciende
    const a = i / 8 * 6.2832, k = eo(prog(lt, 1.4, 1.7));
    line(1500 + Math.cos(a) * 150, cy + Math.sin(a) * 150, 1500 + Math.cos(a) * (150 + 60 * k), cy + Math.sin(a) * (150 + 60 * k), { w: 7, c: C.gold });
  }
  sprite(FOCO, { Y: prendido ? C.gold : C.light, W: C.white, G: C.gray }, 1500, 820, 26, { sq: 1 + 0.04 * Math.sin(lt * 9) });
  X.restore();
});

// ---------- 2. La respuesta (fondo oscuro: cada corte se nota) ----------
escena(CUT[1], CUT[2], lt => {
  bg('dark');
  X.save(); cam(1 + 0.06 * eo(lt / 3), 0, 0, 0, shakeAt(lt, 0.9, 10));
  header('SERVICIOS ALCARAZ', C.or);
  txt('Llegamos el mismo día', 960, 520, { size: 120, wt: 700, c: C.white, reveal: prog(lt, 0.05, 0.6) });
  const p = back(prog(lt, 0.8, 1.1));
  if (p > 0) {
    X.save(); X.translate(960, 760); X.scale(p, p);
    poly([[20, -150], [-70, 10], [-5, 10], [-40, 150], [80, -30], [15, -30], [55, -150]], { fill: C.gold, c: C.ink, w: 6 });
    X.restore();
  }
  X.restore();
  // Lo fijo en pantalla va FUERA de cam(): con el zoom de la escena, el pie se saldria del cuadro.
  txt('Guadalajara · negocio ficticio de ejemplo', 960, 1030, { f: 'Inter', size: 30, wt: 400, c: C.gray });
});
