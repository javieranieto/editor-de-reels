"""Editor de Reels — interfaz grafica.

Doble clic en "Editor de Reels.bat" (o ejecutar: pythonw interfaz.pyw).
Selecciona la carpeta con tus clips, elige el estilo de corte y pulsa Crear.
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import nucleo
from pipeline.cifras import ESTILOS as ESTILOS_CIFRA
from pipeline.letras import ESTILOS as ESTILOS_LETRA

PERFILES = [
    ("dinamico", "Dinámico (recomendado) — corta pausas y muletillas, ritmo de reel"),
    ("conservador", "Conservador — solo corta silencios largos, respeta tu ritmo"),
    ("agresivo", "Agresivo — corta todo lo posible; revisa antes de publicar"),
]
MODELOS = [
    ("medium", "Preciso (medium) — mejor transcripción, algo más lento"),
    ("small", "Rápido (small) — suficiente para pruebas"),
]
CAPTIONS = [
    ("palabra", "Palabra por palabra (1-2 palabras grandes, estilo reel)"),
    ("clasico", "Clásicos — frases completas abajo"),
    ("no", "Sin subtítulos"),
]
def _opciones(estilos, preferido):
    """Desplegable armado desde el modulo, con el elegido primero.

    Se leen de ahi y no se repiten aqui: al podar los estilos rechazados esta
    lista quedo ofreciendo cuatro que ya no existian, y elegir uno habria
    reventado la generacion.
    """
    orden = ([preferido] if preferido in estilos else []) + \
            [k for k in estilos if k != preferido]
    return [(k, "%s — %s" % (k, estilos[k]["descripcion"])) for k in orden]


LETRAS = _opciones(ESTILOS_LETRA, "resalte")
CIFRAS = _opciones(ESTILOS_CIFRA, "pop")
ZOOMS = [
    ("no", "Sin zoom"),
    ("suave", "Suave — acercamiento lento casi imperceptible en cada clip"),
    ("progresivo", "Progresivo — se acerca en cada corte, abre al cambiar de idea"),
    ("punch", "Punch — empuje marcado solo en las frases con énfasis"),
]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Editor de Reels")
        root.geometry("720x640")
        root.minsize(640, 560)

        self.videos = []
        self.cola = queue.Queue()
        self.ocupado = False

        cont = ttk.Frame(root, padding=12)
        cont.pack(fill="both", expand=True)

        # --- paso 1: clips
        paso1 = ttk.LabelFrame(cont, text=" 1. Tus clips (en orden de grabación) ", padding=8)
        paso1.pack(fill="x")
        fila = ttk.Frame(paso1)
        fila.pack(fill="x")
        ttk.Button(fila, text="Elegir carpeta…", command=self.elegir_carpeta).pack(side="left")
        ttk.Button(fila, text="Elegir videos…", command=self.elegir_archivos).pack(side="left", padx=6)
        self.lbl_videos = ttk.Label(fila, text="ningún clip seleccionado", foreground="#888")
        self.lbl_videos.pack(side="left", padx=8)
        self.lista = tk.Listbox(paso1, height=5)
        self.lista.pack(fill="x", pady=(6, 0))

        # --- paso 2: ajustes
        paso2 = ttk.LabelFrame(cont, text=" 2. Ajustes ", padding=8)
        paso2.pack(fill="x", pady=(10, 0))

        ttk.Label(paso2, text="Nombre del proyecto:").grid(row=0, column=0, sticky="w")
        self.var_nombre = tk.StringVar(value=nucleo.nombre_por_defecto())
        ttk.Entry(paso2, textvariable=self.var_nombre, width=32).grid(
            row=0, column=1, sticky="w", padx=6)

        ttk.Label(paso2, text="Estilo de corte:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.var_perfil = tk.StringVar(value=PERFILES[0][1])
        ttk.Combobox(paso2, textvariable=self.var_perfil, state="readonly", width=62,
                     values=[d for _, d in PERFILES]).grid(
            row=1, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(paso2, text="Transcripción:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.var_modelo = tk.StringVar(value=MODELOS[0][1])
        ttk.Combobox(paso2, textvariable=self.var_modelo, state="readonly", width=62,
                     values=[d for _, d in MODELOS]).grid(
            row=2, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(paso2, text="Subtítulos:").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.var_captions = tk.StringVar(value=CAPTIONS[0][1])
        ttk.Combobox(paso2, textvariable=self.var_captions, state="readonly", width=62,
                     values=[d for _, d in CAPTIONS]).grid(
            row=3, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(paso2, text="Letras:").grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.var_letras = tk.StringVar(value=LETRAS[0][1])
        ttk.Combobox(paso2, textvariable=self.var_letras, state="readonly", width=62,
                     values=[d for _, d in LETRAS]).grid(
            row=4, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(paso2, text="Cifras:").grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.var_cifras = tk.StringVar(value=CIFRAS[0][1])
        ttk.Combobox(paso2, textvariable=self.var_cifras, state="readonly", width=62,
                     values=[d for _, d in CIFRAS]).grid(
            row=5, column=1, sticky="w", padx=6, pady=(6, 0))

        ttk.Label(paso2, text="Zoom:").grid(row=6, column=0, sticky="w", pady=(6, 0))
        self.var_zoom = tk.StringVar(value=ZOOMS[0][1])
        ttk.Combobox(paso2, textvariable=self.var_zoom, state="readonly", width=62,
                     values=[d for _, d in ZOOMS]).grid(
            row=6, column=1, sticky="w", padx=6, pady=(6, 0))

        self.var_tomas = tk.BooleanVar(value=True)
        ttk.Checkbutton(paso2, text="Quitar tomas repetidas (usar la última)",
                        variable=self.var_tomas).grid(row=7, column=1, sticky="w", pady=(6, 0))

        ttk.Label(paso2, text="Resultado:").grid(row=8, column=0, sticky="w", pady=(6, 0))
        self.var_salida = tk.StringVar(value="capcut")
        fs = ttk.Frame(paso2)
        fs.grid(row=8, column=1, sticky="w", pady=(6, 0))
        ttk.Radiobutton(fs, text="Proyecto de CapCut (editable)",
                        variable=self.var_salida, value="capcut").pack(side="left")
        ttk.Radiobutton(fs, text="Video MP4 + subtítulos",
                        variable=self.var_salida, value="mp4").pack(side="left", padx=10)

        # --- paso 3: ejecutar
        paso3 = ttk.Frame(cont)
        paso3.pack(fill="x", pady=(10, 0))
        self.btn_plan = ttk.Button(paso3, text="Ver plan (no crea nada)",
                                   command=lambda: self.lanzar(solo_plan=True))
        self.btn_plan.pack(side="left")
        self.btn_crear = ttk.Button(paso3, text="✂  Crear", command=self.lanzar)
        self.btn_crear.pack(side="left", padx=8)
        self.progreso = ttk.Progressbar(paso3, mode="indeterminate", length=180)
        self.progreso.pack(side="left", padx=8)

        # --- registro
        self.texto = tk.Text(cont, height=14, state="disabled", wrap="word",
                             background="#1e1e1e", foreground="#d4d4d4")
        self.texto.pack(fill="both", expand=True, pady=(10, 0))

        self.log("Bienvenido. Elige la carpeta con tus clips y pulsa Crear.")
        self.log("Importante: cierra CapCut antes de crear el proyecto.")
        root.after(200, self.vaciar_cola)

    # ---------- seleccion ----------
    def elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="Carpeta con tus clips")
        if not carpeta:
            return
        self.videos = nucleo.listar_videos(carpeta)
        self.refrescar_lista()
        if not self.videos:
            messagebox.showwarning("Sin videos",
                                   "No encontré videos (.mp4/.mov/…) en esa carpeta.")

    def elegir_archivos(self):
        archivos = filedialog.askopenfilenames(
            title="Elige tus clips",
            filetypes=[("Videos", "*.mp4 *.mov *.mkv *.avi *.m4v"), ("Todos", "*.*")])
        if archivos:
            self.videos = list(archivos)
            self.refrescar_lista()

    def refrescar_lista(self):
        self.lista.delete(0, "end")
        for i, v in enumerate(self.videos, 1):
            self.lista.insert("end", " %d.  %s" % (i, os.path.basename(v)))
        self.lbl_videos.config(
            text="%d clip(s)" % len(self.videos),
            foreground="#2a7" if self.videos else "#888")

    # ---------- ejecucion ----------
    def lanzar(self, solo_plan=False):
        if self.ocupado:
            return
        if not self.videos:
            messagebox.showinfo("Faltan clips", "Primero elige una carpeta o tus videos.")
            return
        nombre = self.var_nombre.get().strip() or nucleo.nombre_por_defecto()
        perfil = next(c for c, d in PERFILES if d == self.var_perfil.get())
        modelo = next(c for c, d in MODELOS if d == self.var_modelo.get())

        self.ocupado = True
        self.btn_crear.config(state="disabled")
        self.btn_plan.config(state="disabled")
        self.progreso.start(12)
        self.log("")
        self.log("=== %s ===" % ("Plan de cortes" if solo_plan else "Creando " + nombre))

        captions = next(c for c, d in CAPTIONS if d == self.var_captions.get())
        zoom = next(c for c, d in ZOOMS if d == self.var_zoom.get())
        letras = next(c for c, d in LETRAS if d == self.var_letras.get())
        cifra = next(c for c, d in CIFRAS if d == self.var_cifras.get())

        hilo = threading.Thread(
            target=self.trabajar,
            args=(list(self.videos), nombre, perfil, modelo,
                  captions, self.var_salida.get(), solo_plan,
                  self.var_tomas.get(), zoom, letras, cifra),
            daemon=True)
        hilo.start()

    def trabajar(self, videos, nombre, perfil, modelo, captions, salida,
                 solo_plan, tomas, zoom, letras="resalte", cifra="pop"):
        try:
            res = nucleo.editar(videos, nombre, perfil=perfil, modelo=modelo,
                                subtitulos=captions != "no", salida=salida,
                                solo_plan=solo_plan, quitar_tomas=tomas,
                                captions=captions, zoom=zoom, letras=letras,
                                cifra=cifra,
                                log=self.cola.put)
            self.cola.put(("__fin__", res, solo_plan, salida))
        except Exception as e:
            self.cola.put(("__error__", str(e)))

    def vaciar_cola(self):
        try:
            while True:
                m = self.cola.get_nowait()
                if isinstance(m, tuple) and m[0] == "__fin__":
                    self.terminar(m[1], m[2], m[3])
                elif isinstance(m, tuple) and m[0] == "__error__":
                    self.fallar(m[1])
                else:
                    self.log(str(m))
        except queue.Empty:
            pass
        self.root.after(200, self.vaciar_cola)

    def terminar(self, res, solo_plan, salida):
        self.progreso.stop()
        self.ocupado = False
        self.btn_crear.config(state="normal")
        self.btn_plan.config(state="normal")
        self.var_nombre.set(nucleo.nombre_por_defecto())
        r = res["resumen"]
        if solo_plan:
            messagebox.showinfo("Plan listo",
                                "Duración: %.1fs → %.1fs (ahorro %.1f%%)\n"
                                "%d cortes, %d muletillas fuera.\n\nNo se creó nada."
                                % (r["duracion_original"], r["duracion_final"],
                                   r["ahorro_pct"], r["trozos"], r["muletillas_eliminadas"]))
            return
        if salida == "mp4":
            if messagebox.askyesno("Listo",
                                   "MP4 creado (ahorro %.1f%%).\n\n¿Abrir la carpeta?"
                                   % r["ahorro_pct"]):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(res["mp4"])])
        else:
            messagebox.showinfo("Listo",
                                "Proyecto creado (ahorro %.1f%%).\n\n"
                                "Abre CapCut y búscalo en tu lista de proyectos."
                                % r["ahorro_pct"])

    def fallar(self, msg):
        self.progreso.stop()
        self.ocupado = False
        self.btn_crear.config(state="normal")
        self.btn_plan.config(state="normal")
        self.log("ERROR: " + msg)
        messagebox.showerror("No se pudo", msg)

    def log(self, texto):
        self.texto.config(state="normal")
        self.texto.insert("end", texto + "\n")
        self.texto.see("end")
        self.texto.config(state="disabled")


if __name__ == "__main__":
    raiz = tk.Tk()
    try:
        raiz.iconbitmap(default="")
    except Exception:
        pass
    App(raiz)
    raiz.mainloop()
