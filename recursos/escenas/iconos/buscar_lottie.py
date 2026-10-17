"""Busca animaciones GRATUITAS en LottieFiles (API pública GraphQL) y baja candidatas para el banco de íconos.
Las públicas van con la Lottie Simple License (uso comercial sin atribución obligatoria; no se revenden sueltas).
Guarda por cada una de dónde salió y quién la hizo (candidatas/fuentes.json) por si un autor pone reglas propias.
Uso: python buscar_lottie.py  ->  candidatas/<tema>_<n>.json + fuentes.json"""
import json, os, urllib.request
AQ = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(AQ, "candidatas"); os.makedirs(C, exist_ok=True)
API = "https://graphql.lottiefiles.com/2022-08"
TEMAS = {"telefono": "phone ringing", "notificacion": "notification bell", "chat": "chat message", "reloj": "clock time",
         "dinero": "money", "calendario": "calendar", "estrellas": "star rating", "pin": "location pin", "grafica": "growth chart",
         "alerta": "warning", "palomita": "success check", "cronometro": "stopwatch", "megafono": "megaphone",
         "apreton": "handshake", "buscar": "search"}
def q(query, n=6):
    body = {"query": 'query{ searchPublicAnimations(query:"%s", first:%d){ edges{ node{ id name jsonUrl url downloads likesCount createdBy{ username } } } } }' % (query, n)}
    r = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    return [e["node"] for e in json.load(urllib.request.urlopen(r, timeout=30))["data"]["searchPublicAnimations"]["edges"]]
fuentes = {}
for tema, consulta in TEMAS.items():
    nodos = sorted(q(consulta), key=lambda n: -(n.get("downloads") or 0))[:4]
    for k, n in enumerate(nodos):
        nombre = "%s_%d" % (tema, k + 1)
        try:
            data = urllib.request.urlopen(urllib.request.Request(n["jsonUrl"], headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
            json.loads(data); open(os.path.join(C, nombre + ".json"), "wb").write(data)
            fuentes[nombre] = {"tema": tema, "titulo": n["name"], "url": n["url"], "autor": (n.get("createdBy") or {}).get("username"),
                               "descargas": n.get("downloads"), "licencia": "Lottie Simple License (gratuita, pública)"}
        except Exception as e:
            print("  falló", nombre, e)
json.dump(fuentes, open(os.path.join(C, "fuentes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(fuentes), "candidatas")
