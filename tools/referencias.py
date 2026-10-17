# -*- coding: utf-8 -*-
"""Saca de los videos de una persona un catalogo de fotogramas de REFERENCIA.

Para que sirve: un disenador que va a generar video con IA -Seedance, o
cualquier modelo de imagen a video- necesita una imagen de partida por toma.
Con una sola foto el parecido se va derivando; con un catalogo variado elige
la que encaja con lo que quiere generar y el personaje se sostiene.

El problema de sacar "un frame cada 5 segundos" es que la mayoria no sirven:
en un video hablado la cara esta medio borrosa por el movimiento, con la mano
delante, o con los ojos cerrados. Asi que aqui NO se muestrea a ciegas: se
detecta la cara, se MIDE cada fotograma y se elige.

Lo que se mide, y por que:

  nitidez   varianza del laplaciano sobre el recorte de la cara, llevado antes
            a un tamano fijo. Asi la cifra compara "esta cara esta crujiente o
            barrida" entre archivos de 1080 y de 4K, que es lo que importa; el
            tamano de la cara se juzga aparte porque es otra cosa.
  cara_px   alto de la cara en pixeles del ORIGINAL. Manda mas que la
            resolucion del archivo: en un 4K vertical la cara mide el triple
            que en un 1080 horizontal, y es lo unico que decide cuanto
            detalle real llega.
  giro      de los 5 puntos de YuNet (ojo der, ojo izq, nariz, comisuras).
            Sirve para repartir: un catalogo de 40 frontales no le da al
            modelo ni un perfil del que tirar.
  ladeo     inclinacion de la linea de los ojos.
  ojos      proxy de ojo abierto. Es una HEURISTICA y por eso no descarta
            sola: ordena la hoja de contactos para que el parpadeo salte a la
            vista. Lo que cierra un caso aqui es mirar.

Lo que NO puede medir, y por eso el resultado se MIRA siempre: si tiene la
mano delante de la cara, si la mueca es rara, si el gesto sirve. La hoja de
contactos existe para eso.

Dos pasadas a proposito:
  1. barrido a 640 px de ancho para encontrar candidatos. Barato.
  2. sobre los finalistas, se vuelve al archivo y se mide la nitidez EN LA
     RESOLUCION REAL. Medir la nitidez en la miniatura es medir otra cosa.

Uso:
    python tools/referencias.py --nombre "presentador" \
        --fuente "C:/.../camara.mp4" \
        --fuente "C:/.../otro.mp4@0-182,1098-1173" \
        --cuantos 40
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = os.path.join(RAIZ, 'recursos', 'yunet.onnx')
SALIDA = os.path.join(RAIZ, 'proyectos', '_referencias')

ANCHO_BARRIDO = 640      # a lo que se reduce para detectar
FPS_BARRIDO = 2.0        # fotogramas por segundo que se miran
CONFIANZA = 0.80         # score minimo de YuNet para creerse la cara
LADO_NITIDEZ = 160       # la cara se lleva a este cuadro antes de medirla
HUECO_MIN = 3.0          # segundos entre dos elegidos de la misma fuente
HASH_MIN = 8             # bits de diferencia para no considerarlas la misma
MARGEN_CARA = 0.5        # aire alrededor de la cara en el recorte, en altos
SUELO_NITIDEZ = 0.55     # fraccion de la MEDIANA de su fuente por debajo de
                         # la cual no entra, aunque su pose se quede vacia
NUCLEO = 0.35            # cuanto se ensancha la caja de los 5 puntos
SALTO_MAX = 0.9          # altos de cara que puede alejarse una deteccion de
                         # la mediana de su clip antes de darla por falsa
MUESTRAS_SALTO = 8       # por debajo de esto la mediana no dice nada

# Sube esto al cambiar COMO se producen las medidas del barrido, o las caches
# viejas taparan la mejora. Es la misma leccion que la clave de idioma de
# transcribe.py: una cache que no incluye lo que cambio devuelve lo de antes
# en silencio.
FORMATO_BARRIDO = 2


# --------------------------------------------------------------- deteccion

_det = None


def _detector(w, h):
    global _det
    if _det is None:
        if not os.path.exists(MODELO):
            sys.exit('Falta el modelo: %s' % MODELO)
        _det = cv2.FaceDetectorYN.create(MODELO, '', (w, h), 0.5, 0.3, 5000)
    _det.setInputSize((w, h))
    return _det


def _mayor(img):
    """La cara mas grande de la imagen: (caja, puntos, score) o None.

    La mas grande y no la de mejor score a proposito: en estos videos solo hay
    una persona, y lo que aparece de vez en cuando al fondo -una foto en la
    pared, una cara en la pantalla- siempre es mas chico.
    """
    h, w = img.shape[:2]
    _, caras = _detector(w, h).detect(img)
    if caras is None or not len(caras):
        return None
    c = max(caras, key=lambda f: f[3])
    return c[:4], c[4:14].reshape(5, 2), float(c[-1])


def _nucleo(puntos, w, h):
    """Caja de los 5 puntos ensanchada: ojos, nariz y boca, y nada mas.

    Se mide aqui y no en la caja del detector por un fallo real: en un reel ya
    terminado la caja se comia un subtitulo quemado, y un texto amarillo sobre
    negro tiene tanto contraste que la varianza del laplaciano se disparo a
    16378 cuando el resto del lote andaba por 2500. O sea que el fotograma
    "mas nitido" del catalogo lo era por el texto, no por la cara. Los puntos
    no se pueden enganar asi: caen dentro de la cara por definicion.
    """
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    ax, ay = (x1 - x0) * NUCLEO, (y1 - y0) * NUCLEO
    return (max(0, int(x0 - ax)), max(0, int(y0 - ay)),
            min(w, int(x1 + ax)), min(h, int(y1 + ay)))


def _nitidez(gris_cara):
    """Varianza del laplaciano sobre la cara llevada a un cuadro fijo.

    El tamano fijo es lo que hace la cifra comparable entre un 1080 y un 4K:
    sin el, un archivo con mas pixeles saca mas varianza aunque este igual de
    barrido.
    """
    if gris_cara.size == 0:
        return 0.0
    chico = cv2.resize(gris_cara, (LADO_NITIDEZ, LADO_NITIDEZ))
    return float(cv2.Laplacian(chico, cv2.CV_64F).var())


def _giro(puntos):
    """-1 mira a su izquierda .. 0 de frente .. +1 mira a su derecha."""
    ojo_d, ojo_i, nariz = puntos[0], puntos[1], puntos[2]
    izq = float(nariz[0] - ojo_d[0])
    der = float(ojo_i[0] - nariz[0])
    if izq + der <= 0:
        return 0.0
    return round((izq - der) / (izq + der), 3)


def _ladeo(puntos):
    """Grados de inclinacion de la linea de los ojos."""
    ojo_d, ojo_i = puntos[0], puntos[1]
    return round(float(np.degrees(np.arctan2(ojo_i[1] - ojo_d[1],
                                             ojo_i[0] - ojo_d[0]))), 1)


def _ojos(gris, puntos, alto_cara):
    """Proxy de ojo abierto: contraste local alrededor de los dos ojos.

    Un ojo abierto trae pupila e iris, o sea pixeles muy oscuros junto a la
    esclerotica; uno cerrado es un parpado liso. NO decide nada por si solo
    -es una heuristica y ya nos mordio una en este repo-: se guarda para
    ordenar la revision.
    """
    lado = max(4, int(alto_cara * 0.22))
    vals = []
    for (x, y) in puntos[:2]:
        x, y = int(x), int(y)
        p = gris[max(0, y - lado // 2):y + lado // 2,
                 max(0, x - lado):x + lado]
        if p.size:
            vals.append(float(p.std()))
    return round(float(np.mean(vals)) if vals else 0.0, 1)


def _hash(gris_cara):
    """dHash de 64 bits sobre la cara, para no repetir la misma pose."""
    chico = cv2.resize(gris_cara, (9, 8))
    bits = chico[:, 1:] > chico[:, :-1]
    v = 0
    for b in bits.flatten():
        v = (v << 1) | int(b)
    return v


def _dist(a, b):
    return bin(a ^ b).count('1')


# ------------------------------------------------------------ pasada 1

def _duracion(src):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'format=duration', '-of', 'csv=p=0', src],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def _tamano(src):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=width,height',
                          '-of', 'csv=p=0:s=x', src],
                         capture_output=True, text=True).stdout.strip()
    w, h = out.split('x')[:2]
    return int(w), int(h)


def _clave(src, tramos):
    """Todo lo que cambia los numeros del barrido entra en la clave.

    Si algo que los cambia se queda fuera, la cache devuelve los de antes sin
    avisar y la mejora no aparece nunca. Ya paso en este repo con el idioma de
    whisper: la cache validaba modelo y formato pero no el idioma, asi que
    volver a correr con `--idioma en` devolvia la transcripcion en espanol.
    """
    st = os.stat(src)
    crudo = '|'.join(str(x) for x in [
        FORMATO_BARRIDO, os.path.abspath(src), int(st.st_mtime), st.st_size,
        FPS_BARRIDO, ANCHO_BARRIDO, CONFIANZA, NUCLEO, LADO_NITIDEZ, tramos])
    import hashlib
    return hashlib.md5(crudo.encode('utf-8')).hexdigest()[:16]


def barrido_cacheado(src, tramos, etiqueta, carpeta):
    """El barrido de esta fuente, del disco si ya se hizo igual."""
    cache = os.path.join(carpeta, '_barrido')
    os.makedirs(cache, exist_ok=True)
    ruta = os.path.join(cache, _clave(src, tramos) + '.json')
    if os.path.exists(ruta):
        with open(ruta, encoding='utf-8') as fh:
            lote = json.load(fh)
        for c in lote:                     # el nombre puede haber cambiado
            c['fuente'] = etiqueta
        return lote, True
    lote = barrer(src, tramos, etiqueta)
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(lote, fh)
    return lote, False


def barrer(src, tramos, etiqueta):
    """Mide un fotograma cada 1/FPS_BARRIDO segundos. Devuelve lista de dicts."""
    w0, h0 = _tamano(src)
    escala = ANCHO_BARRIDO / float(w0)
    w = ANCHO_BARRIDO
    h = int(round(h0 * escala / 2)) * 2
    hallados = []
    for (ini, fin) in tramos:
        cmd = ['ffmpeg', '-v', 'error', '-ss', '%.3f' % ini, '-i', src,
               '-t', '%.3f' % (fin - ini),
               '-vf', 'fps=%s,scale=%d:%d' % (FPS_BARRIDO, w, h),
               '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
        pr = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        n = w * h * 3
        i = -1
        while True:
            buf = pr.stdout.read(n)
            if len(buf) < n:
                break
            i += 1
            img = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            hit = _mayor(img)
            if hit is None:
                continue
            caja, puntos, score = hit
            if score < CONFIANZA:
                continue
            x, y, cw, ch = [int(v) for v in caja]
            if ch < 20:
                continue
            gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            nx0, ny0, nx1, ny1 = _nucleo(puntos, w, h)
            cara = gris[ny0:ny1, nx0:nx1]
            if cara.size == 0:
                continue
            hallados.append({
                'fuente': etiqueta,
                'grupo': os.path.basename(os.path.dirname(src)),
                'src': src,
                'seg': round(ini + i / FPS_BARRIDO, 3),
                'cara_px': int(round(ch / escala)),
                'nitidez': round(_nitidez(cara), 1),
                'giro': _giro(puntos),
                'ladeo': _ladeo(puntos),
                'ojos': _ojos(gris, puntos, ch),
                'brillo': round(float(cara.mean()), 1),
                'score': round(score, 3),
                'hash': _hash(cara),
                'caja': (x / escala, y / escala, cw / escala, ch / escala),
                'nucleo': (nx0 / escala, ny0 / escala,
                           nx1 / escala, ny1 / escala),
            })
        pr.stdout.close()
        pr.wait()
    return hallados


# ------------------------------------------------------------ eleccion

def _cubo(giro):
    if giro <= -0.30:
        return 'perfil izq'
    if giro <= -0.10:
        return 'tres cuartos izq'
    if giro < 0.10:
        return 'frontal'
    if giro < 0.30:
        return 'tres cuartos der'
    return 'perfil der'


def sin_saltos(cands):
    """Tira las detecciones que se van de donde esta la cara en su clip.

    YuNet acierta casi siempre, pero de vez en cuando llama cara a un trozo de
    torso. Aqui paso una vez en 5762 fotogramas y el destrozo fue grande: la
    "cara" era la camisa de puntos con un subtitulo encima, y ese patron fino
    mas el texto dispararon la nitidez a 11804 sobre un lote de 1500. O sea
    que el fotograma que salia elegido como el MEJOR del catalogo era el unico
    que no tenia cara. El score no lo filtro -dio 0.82, por encima del corte-.

    Lo que si lo delata es que en un video de camara fija la cara NO salta. Se
    midio sobre las 13 fuentes reales: en material sano la deteccion mas
    alejada de la mediana de su clip esta a 0.81 altos de cara, y las dos
    falsas a 1.04 y 1.15. El corte va en medio.

    ⚠️ Da por hecha una camara fija, que es como graba el. Con una camara que
    se mueva o un plano que cambie, la mediana del clip no significa nada y
    esto habria que apagarlo.
    """
    por = {}
    for c in cands:
        por.setdefault(c['fuente'], []).append(c)
    vivos, fuera = [], []
    for lote in por.values():
        if len(lote) < MUESTRAS_SALTO:
            vivos += lote
            continue
        cys = sorted(c['caja'][1] + c['caja'][3] / 2 for c in lote)
        altos = sorted(c['caja'][3] for c in lote)
        mcy, malto = cys[len(cys) // 2], altos[len(altos) // 2]
        for c in lote:
            cy = c['caja'][1] + c['caja'][3] / 2
            if malto > 0 and abs(cy - mcy) / malto > SALTO_MAX:
                fuera.append(c)
            else:
                vivos.append(c)
    if fuera:
        print('  %d detecciones fuera de sitio (no era una cara)' % len(fuera))
    return vivos


def _cupo(elegidos, c, por_fuente, por_grupo):
    """True si este candidato ya no cabe por su cupo de archivo o de carpeta.

    El cupo por CARPETA hace falta porque una tanda grabada el mismo dia suele
    venir partida en varios archivos: nueve clips de una sesion son, para el
    modelo, un solo look, y sin este tope se llevaban media seleccion.
    """
    if por_fuente and sum(1 for e in elegidos
                          if e['fuente'] == c['fuente']) >= por_fuente:
        return True
    if por_grupo and sum(1 for e in elegidos
                         if e['grupo'] == c['grupo']) >= por_grupo:
        return True
    return False


def elegir(cands, cuantos, por_fuente=None, por_grupo=None):
    """Se queda con los mejores repartiendo entre fuentes y entre poses.

    Reparte a proposito: 40 fotogramas frontales del mismo minuto son, para el
    modelo, una sola foto repetida 40 veces. Lo que le da de donde tirar es la
    variedad de angulo y de gesto.
    """
    if not cands:
        return []
    # umbral de nitidez POR FUENTE: cada camara y cada iluminacion tienen su
    # nivel, y un umbral global se llevaria una fuente entera por delante.
    por_src = {}
    for c in cands:
        por_src.setdefault(c['fuente'], []).append(c)
    vivos = []
    for etiqueta, lote in por_src.items():
        nit = sorted(x['nitidez'] for x in lote)
        corte = nit[int(len(nit) * 0.55)]      # se descarta la mitad borrosa
        # Y ademas un suelo contra el mejor de esa misma fuente. Sin el, un
        # grupo de pose con pocos candidatos mete su mejor aunque ese mejor
        # este barrido: el reparto no puede pesar mas que la calidad.
        suelo = nit[int(len(nit) * 0.90)] * SUELO_NITIDEZ
        vivos += [x for x in lote
                  if x['nitidez'] >= corte and x['nitidez'] >= suelo]

    grupos = {}
    for c in vivos:
        grupos.setdefault((c['fuente'], _cubo(c['giro'])), []).append(c)
    for g in grupos.values():
        g.sort(key=lambda c: -c['nitidez'])

    elegidos = []
    # ronda por grupos, para no vaciar el mejor y dejar los demas sin nada
    claves = sorted(grupos, key=lambda k: -len(grupos[k]))
    while len(elegidos) < cuantos:
        metio = False
        for k in claves:
            if len(elegidos) >= cuantos:
                break
            for c in grupos[k]:
                if c.get('_usado'):
                    continue
                if _cupo(elegidos, c, por_fuente, por_grupo):
                    break
                cerca = any(e['fuente'] == c['fuente']
                            and abs(e['seg'] - c['seg']) < HUECO_MIN
                            for e in elegidos)
                if cerca:
                    c['_usado'] = True
                    continue
                if any(_dist(e['hash'], c['hash']) < HASH_MIN for e in elegidos):
                    c['_usado'] = True
                    continue
                c['_usado'] = True
                elegidos.append(c)
                metio = True
                break
        if not metio:
            break
    return elegidos


# ------------------------------------------------------------ salida

def _sacar(src, seg, destino):
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % seg, '-i', src,
                    '-frames:v', '1', '-q:v', '2', destino, '-y'],
                   capture_output=True)
    return os.path.exists(destino)


def medir_real(cands, tmp):
    """Saca cada candidato a resolucion nativa y le mide la nitidez de verdad.

    Hace falta una pasada aparte porque la del barrido se midio sobre una
    miniatura de 640 px: sirve para ordenar candidatos y nada mas. Un
    fotograma puede parecer limpio reducido y estar barrido en el original, y
    entonces se estaria filtrando por un numero y entregando otro.
    """
    os.makedirs(tmp, exist_ok=True)
    vivos = []
    for i, c in enumerate(cands):
        ruta = os.path.join(tmp, 'c%04d.jpg' % i)
        if not _sacar(c['src'], c['seg'], ruta):
            continue
        img = cv2.imread(ruta)
        if img is None:
            continue
        nx0, ny0, nx1, ny1 = [int(v) for v in c['nucleo']]
        gris = cv2.cvtColor(img[ny0:ny1, nx0:nx1], cv2.COLOR_BGR2GRAY)
        c['nitidez_real'] = round(_nitidez(gris), 1)
        c['ruta'] = ruta
        vivos.append(c)
    return vivos


def podar(medidos, cuantos, por_fuente=None, por_grupo=None):
    """Deja los mejores por nitidez REAL, sin perder el reparto de poses."""
    por_src = {}
    for c in medidos:
        por_src.setdefault(c['fuente'], []).append(c)
    vivos = []
    fuera = 0
    for etiqueta, lote in por_src.items():
        nit = sorted(x['nitidez_real'] for x in lote)
        # contra la MEDIANA, no contra el mejor. Con el p90 de una muestra de
        # ocho, un solo fotograma excepcionalmente nitido le subia la vara a
        # todos los demas de su fuente: un video de 26 minutos aportaba UNO,
        # mientras otro de calidad identica aportaba seis solo porque no tenia
        # ese pico. La mediana no se deja arrastrar por un extremo.
        suelo = nit[len(nit) // 2] * SUELO_NITIDEZ
        buenos = [x for x in lote if x['nitidez_real'] >= suelo]
        fuera += len(lote) - len(buenos)
        vivos += buenos
    if fuera:
        print('  %d descartados por barridos al medirlos en resolucion real'
              % fuera)

    grupos = {}
    for c in vivos:
        grupos.setdefault((c['fuente'], _cubo(c['giro'])), []).append(c)
    for g in grupos.values():
        g.sort(key=lambda c: -c['nitidez_real'])

    fin = []
    idx = {k: 0 for k in grupos}
    claves = sorted(grupos, key=lambda k: -len(grupos[k]))
    while len(fin) < cuantos:
        metio = False
        for k in claves:
            if len(fin) >= cuantos:
                break
            if idx[k] < len(grupos[k]):
                c = grupos[k][idx[k]]
                idx[k] += 1
                if _cupo(fin, c, por_fuente, por_grupo):
                    continue
                fin.append(c)
                metio = True
        if not metio:
            break
    return fin


def escribir(finalistas, carpeta):
    """Deja el fotograma entero y el recorte de cara, ya numerados."""
    fot = os.path.join(carpeta, 'fotogramas')
    car = os.path.join(carpeta, 'caras')
    for d in (fot, car):
        os.makedirs(d, exist_ok=True)
    filas = []
    orden = sorted(finalistas, key=lambda x: (x['fuente'], x['seg']))
    for i, c in enumerate(orden, 1):
        base = '%02d %s %07.1fs' % (i, c['fuente'], c['seg'])
        img = cv2.imread(c['ruta'])
        if img is None:
            continue
        cv2.imwrite(os.path.join(fot, base + '.jpg'), img,
                    [cv2.IMWRITE_JPEG_QUALITY, 95])
        H, W = img.shape[:2]
        x, y, w, h = c['caja']
        cx, cy = x + w / 2, y + h / 2
        lado = h * (1 + 2 * MARGEN_CARA)
        x0, y0 = int(max(0, cx - lado / 2)), int(max(0, cy - lado / 2))
        x1, y1 = int(min(W, cx + lado / 2)), int(min(H, cy + lado / 2))
        recorte = img[y0:y1, x0:x1]
        if recorte.size:
            cv2.imwrite(os.path.join(car, base + '.jpg'), recorte,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
        filas.append({
            'archivo': base + '.jpg',
            'fuente': c['fuente'],
            'segundo': c['seg'],
            'cara_px': c['cara_px'],
            'nitidez_real': c['nitidez_real'],
            'nitidez_barrido': c['nitidez'],
            'pose': _cubo(c['giro']),
            'giro': c['giro'],
            'ladeo': c['ladeo'],
            'ojos': c['ojos'],
            'brillo': c['brillo'],
        })
    if filas:
        with open(os.path.join(carpeta, 'medidas.csv'), 'w', newline='',
                  encoding='utf-8') as fh:
            wr = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
            wr.writeheader()
            wr.writerows(filas)
    return filas


def contactos(carpeta, sub='caras', ancho=5, lado=300):
    """Hoja de contactos: la unica forma de juzgar lo que la medicion no ve.

    Sale numerada para poder decir "fuera la 7 y la 19" sin abrir carpetas.
    """
    d = os.path.join(carpeta, sub)
    if not os.path.isdir(d):
        return []
    nombres = sorted(x for x in os.listdir(d) if x.lower().endswith('.jpg'))
    hojas = []
    por_hoja = ancho * 4
    for n0 in range(0, len(nombres), por_hoja):
        lote = nombres[n0:n0 + por_hoja]
        celdas = []
        for nom in lote:
            img = cv2.imread(os.path.join(d, nom))
            if img is None:
                continue
            h, w = img.shape[:2]
            e = lado / float(max(w, h))
            img = cv2.resize(img, (int(w * e), int(h * e)))
            lienzo = np.zeros((lado, lado, 3), np.uint8)
            yy = (lado - img.shape[0]) // 2
            xx = (lado - img.shape[1]) // 2
            lienzo[yy:yy + img.shape[0], xx:xx + img.shape[1]] = img
            cv2.rectangle(lienzo, (0, 0), (46, 22), (0, 0, 0), -1)
            cv2.putText(lienzo, nom.split()[0], (4, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            celdas.append(lienzo)
        if not celdas:
            continue
        while len(celdas) % ancho:
            celdas.append(np.zeros((lado, lado, 3), np.uint8))
        filas = [np.hstack(celdas[i:i + ancho])
                 for i in range(0, len(celdas), ancho)]
        ruta = os.path.join(carpeta, 'CONTACTOS %s %02d.jpg'
                            % (sub, n0 // por_hoja + 1))
        cv2.imwrite(ruta, np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 88])
        hojas.append(ruta)
    return hojas


# ------------------------------------------------------------ cli

def quitar(carpeta, numeros):
    """Aparta los fotogramas que la revision descarto, por su numero.

    Van a `descartados/` en vez de borrarse: si luego resulta que uno se
    descarto de mas, esta ahi. Y NO se renumera lo que queda -los numeros son
    los de la hoja de contactos que se acaba de mirar, y renumerarlos obliga a
    volver a mirarla entera-.
    """
    fuera = set(numeros)
    movidos = 0
    for sub in ('fotogramas', 'caras'):
        d = os.path.join(carpeta, sub)
        if not os.path.isdir(d):
            continue
        papelera = os.path.join(carpeta, 'descartados', sub)
        os.makedirs(papelera, exist_ok=True)
        for nom in os.listdir(d):
            try:
                n = int(nom.split()[0])
            except (ValueError, IndexError):
                continue
            if n in fuera:
                shutil.move(os.path.join(d, nom), os.path.join(papelera, nom))
                movidos += 1
    for viejo in os.listdir(carpeta):
        if viejo.startswith('CONTACTOS'):
            os.remove(os.path.join(carpeta, viejo))
    hojas = contactos(carpeta, 'caras') + contactos(carpeta, 'fotogramas')
    print('apartados %d archivos (%d fotogramas)' % (movidos, len(fuera)))
    for h in hojas:
        print('   %s' % os.path.basename(h))
    return movidos


def _fuente(txt):
    """'ruta' o 'ruta@ini-fin,ini-fin' -> (ruta, [(ini, fin), ...])."""
    if '@' in txt:
        ruta, rangos = txt.rsplit('@', 1)
        try:
            tramos = []
            for r in rangos.split(','):
                a, b = r.split('-')
                tramos.append((float(a), float(b)))
            return ruta, tramos
        except ValueError:
            pass
    return txt, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--nombre', required=True)
    ap.add_argument('--fuente', action='append',
                    help='ruta, o ruta@ini-fin,ini-fin en segundos')
    ap.add_argument('--cuantos', type=int, default=40)
    ap.add_argument('--por-fuente', type=int, default=None,
                    help='tope de elegidos por archivo')
    ap.add_argument('--por-grupo', type=int, default=None,
                    help='tope por CARPETA: varios clips de una misma sesion '
                         'son un solo look y no deben llevarse la seleccion')
    ap.add_argument('--salida', default=None)
    ap.add_argument('--quitar', default=None,
                    help='numeros a apartar de un catalogo ya hecho, "4,7,12"')
    args = ap.parse_args()

    try:
        from pipeline import entorno
        entorno.consola_utf8()
    except Exception:
        pass

    carpeta = args.salida or os.path.join(SALIDA, args.nombre)
    os.makedirs(carpeta, exist_ok=True)

    if args.quitar:
        nums = [int(x) for x in args.quitar.replace(' ', '').split(',') if x]
        quitar(carpeta, nums)
        return

    if not args.fuente:
        sys.exit('Hace falta al menos un --fuente (o --quitar sobre uno ya hecho)')

    cands = []
    for txt in args.fuente:
        ruta, tramos = _fuente(txt)
        if not os.path.exists(ruta):
            print('NO ESTA: %s' % ruta)
            continue
        dur = _duracion(ruta)
        if tramos is None:
            tramos = [(0.0, dur)]
        etiqueta = os.path.splitext(os.path.basename(ruta))[0][:28]
        total = sum(b - a for a, b in tramos)
        print('barriendo %-30s %5.0f s ...' % (etiqueta, total), end='', flush=True)
        lote, de_cache = barrido_cacheado(ruta, tramos, etiqueta, carpeta)
        print(' %d con cara%s' % (len(lote), ' (cache)' if de_cache else ''))
        cands += lote

    if not cands:
        sys.exit('Ninguna cara encontrada. Revisa las rutas y los tramos.')

    cands = sin_saltos(cands)

    # se preselecciona el doble a proposito: la nitidez que decide es la que
    # se mide en la resolucion real, y esa solo se puede medir sacando el
    # fotograma. Sobran los que no aguanten esa segunda vara.
    elegidos = elegir(cands, args.cuantos * 2, args.por_fuente, args.por_grupo)
    print('\npreseleccionados %d de %d candidatos' % (len(elegidos), len(cands)))
    tmp = os.path.join(carpeta, '_medidos')
    medidos = medir_real(elegidos, tmp)
    finalistas = podar(medidos, args.cuantos, args.por_fuente, args.por_grupo)
    print('finalistas %d' % len(finalistas))
    filas = escribir(finalistas, carpeta)
    shutil.rmtree(tmp, ignore_errors=True)
    hojas = contactos(carpeta, 'caras')
    hojas += contactos(carpeta, 'fotogramas')

    print('\n%-30s %8s %8s %18s %6s'
          % ('archivo', 'cara px', 'nitidez', 'pose', 'ojos'))
    for f in filas:
        print('%-30s %8d %8.0f %18s %6.1f'
              % (f['archivo'][:30], f['cara_px'], f['nitidez_real'],
                 f['pose'], f['ojos']))
    print('\n-> %s' % carpeta)
    for h in hojas:
        print('   %s' % os.path.basename(h))
    print('\nAHORA MIRA LAS HOJAS DE CONTACTOS. La medicion no ve una mano')
    print('delante de la cara, un parpadeo ni una mueca rara.')


if __name__ == '__main__':
    main()
