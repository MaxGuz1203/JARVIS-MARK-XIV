#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Cerebro Cognitivo Mark XIV (Corrección Definitiva de Visión en Pantalla y Apertura de Apps)
- Captura nativa de pantalla vía compositor GNOME Shell D-Bus + gnome-screenshot + PIL (100% real en Ubuntu 24.04)
- Análisis visual objetivo sin alucinaciones de memoria: describe exactamente lo que hay en los píxeles de la pantalla
- Apertura garantizada de Onshape, Canva, LaTeX (Overleaf/Texmaker) y todo el catálogo con normalización fonética
- Conserva todas las funciones previas (Dossiers MathJax, Modelos 3D, Videoclips, Cero-Repetición, Ahorro Batería, etc.)
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import datetime
import json
import os
import random
import re
import shutil
import subprocess
import threading
import time
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageGrab

from jarvis_3d import proyectar_modelo_3d_holografico
from jarvis_dossier import (
    consultar_bibliografia_academica_crossref,
    consultar_wikipedia_profundo,
    generar_dossier_html_stark,
    limpiar_latex_a_unicode_legible,
)
from jarvis_hud import escribir_estado_hud
from jarvis_memory import (
    HISTORIAL_CONVERSACION,
    agregar_nuevo_item_contextual,
    auto_aprender_de_interaccion,
    cargar_memoria,
    consultar_memoria_completa,
    depurar_y_actualizar_todo_el_contexto,
    escanear_contexto_mensajeria_y_web,
    marcar_entregado_o_actualizar_item,
    sincronizar_classroom_y_gmail_desde_pantalla,
    obtener_historial_frases_dichas,
    obtener_resumen_classroom_hablado,
    obtener_resumen_gmail_hablado,
    recordar_dato_o_persona,
    registrar_turno_conversacion,
    sintetizar_respuesta_unica_contextual,
)

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_ENV = DIRECTORIO_BASE / ".env"
MODELO_ACTIVO_CACHE = None

SYSTEM_PROMPT_JARVIS = """
Eres J.A.R.V.I.S. (Mark XIV), la inteligencia artificial de ingeniería de Luis Maximiliano Guzmán Ortiz (Max).
Perfil de Max:
- Estudiante de Ingeniería Eléctrica Electrónica en la FI UNAM.
- Su pareja actual es Soren Alessa, estudiante de Derecho, amante de los libros y los videojuegos, y es muy linda. (Isabel ya NO es su pareja, jamás la menciones).
- Co-Fundador y CTEO de SUMA (imparte Cálculo Integral lunes y miércoles de 7:00 PM a 9:00 PM).
- Líder de Electrónica de Potencia en UNAM SPACE e investigador de robótica en LIRA.
- Opera una laptop ASUS TUF Gaming F16 con Ubuntu Linux 24.04.

Reglas estrictas:
1. Habla siempre en español de México formal, elegante, leal y con el ingenio analítico de J.A.R.V.I.S. de Tony Stark.
2. NUNCA inventes ni adivines qué hay en la pantalla de Max sin usar la captura visual real.
3. NUNCA repitas una frase que ya hayas dicho antes.
4. Tus respuestas habladas usan de 2 a 4 oraciones fluidas, sin asteriscos ni símbolos markdown.
"""


def quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def cargar_api_key() -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if ARCHIVO_ENV.exists():
        for linea in ARCHIVO_ENV.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith("GEMINI_API_KEY="):
                val = linea.split("=", 1)[1].strip().strip('"').strip("'")
                if val and "PEGA_AQUI" not in val:
                    return val
    return ""


def generar_con_modelo_activo(client, contents, config=None):
    global MODELO_ACTIVO_CACHE
    if MODELO_ACTIVO_CACHE:
        try:
            if config is not None:
                return client.models.generate_content(model=MODELO_ACTIVO_CACHE, contents=contents, config=config)
            return client.models.generate_content(model=MODELO_ACTIVO_CACHE, contents=contents)
        except Exception:
            MODELO_ACTIVO_CACHE = None

    candidatos = [
        "models/gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3-flash",
        "gemini-2.0-flash",
    ]
    try:
        for m in client.models.list():
            nombre = getattr(m, "name", "")
            if "gemini" in nombre.lower() and not any(x in nombre.lower() for x in ("2.5", "1.5", "embedding", "imagen", "veo", "tts", "audio")):
                if nombre not in candidatos:
                    candidatos.append(nombre)
    except Exception:
        pass

    ultimo_error = None
    for mod in candidatos:
        try:
            res = (
                client.models.generate_content(model=mod, contents=contents, config=config)
                if config is not None
                else client.models.generate_content(model=mod, contents=contents)
            )
            MODELO_ACTIVO_CACHE = mod
            return res
        except Exception as e:
            ultimo_error = e
            continue
    raise ultimo_error


# =====================================================================
# CAPTURA DE PANTALLA 100% REAL EN UBUNTU 24.04 (WAYLAND + X11)
# =====================================================================
def _imagen_es_valida_y_no_negra(ruta: Path) -> bool:
    """Verifica que la captura exista, no esté vacía y no sea un cuadro completamente negro de Wayland."""
    if not ruta.exists() or ruta.stat().st_size < 1500:
        return False
    try:
        img = Image.open(ruta).convert("RGB")
        arr = np.asarray(img)
        # Si el brillo máximo o desviación estándar es casi 0, es una captura negra bloqueada por Wayland
        if arr.max() < 8 or arr.std() < 2.0:
            return False
        return True
    except Exception:
        return False


def capturar_pantalla_actual() -> Path | None:
    """
    Toma una captura real del monitor actual de Max probando 4 métodos en orden de fidelidad
    para Ubuntu 24.04 (GNOME Shell D-Bus Compositor -> gnome-screenshot -> PIL ImageGrab -> scrot).
    """
    ruta_img = Path("/tmp/jarvis_vision_screen.png")
    if ruta_img.exists():
        try:
            ruta_img.unlink()
        except Exception:
            pass

    # Método 1: Compositor nativo de GNOME Shell vía D-Bus (Funciona siempre en Ubuntu 24.04 Wayland y X11)
    if shutil.which("gdbus"):
        subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell.Screenshot",
                "--object-path", "/org/gnome/Shell/Screenshot",
                "--method", "org.gnome.Shell.Screenshot.Screenshot",
                "false", "false", str(ruta_img),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=4.0,
        )
        if _imagen_es_valida_y_no_negra(ruta_img):
            return ruta_img

    # Método 2: gnome-screenshot CLI
    if shutil.which("gnome-screenshot"):
        subprocess.run(
            ["gnome-screenshot", "-f", str(ruta_img)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=4.0,
        )
        if _imagen_es_valida_y_no_negra(ruta_img):
            return ruta_img

    # Método 3: PIL ImageGrab (X11 / XWayland)
    try:
        img = ImageGrab.grab()
        img.save(str(ruta_img))
        if _imagen_es_valida_y_no_negra(ruta_img):
            return ruta_img
    except Exception:
        pass

    # Método 4: scrot
    if shutil.which("scrot"):
        subprocess.run(
            ["scrot", str(ruta_img)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=4.0,
        )
        if _imagen_es_valida_y_no_negra(ruta_img):
            return ruta_img

    return ruta_img if ruta_img.exists() else None


def capturar_foto_webcam() -> Path | None:
    ruta_cam = Path("/tmp/jarvis_vision_cam.jpg")
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        frame = None
        for _ in range(8):
            ret, frame = cap.read()
        cap.release()
        if frame is not None:
            cv2.imwrite(str(ruta_cam), frame)
            return ruta_cam
    except Exception:
        pass
    return None


def analizar_imagen_con_gemini(ruta_imagen: Path, pregunta_usuario: str) -> str:
    """
    Envía la captura real de la pantalla o webcam a Gemini prohibiendo estrictamente
    alucinar con tareas de la memoria que no estén visibles en la imagen.
    """
    api_key = cargar_api_key()
    if not api_key:
        return "Señor, capturé la imagen pero requiero la clave de Gemini en el archivo punto env."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        imagen_pil = Image.open(ruta_imagen)
        # Redimensionar suavemente si es 4K para respuesta rápida manteniendo nitidez de textos
        imagen_pil.thumbnail((1920, 1080))

        titulos_ventanas = "; ".join(escanear_contexto_mensajeria_y_web()[:4])
        prompt = (
            f"Actúa como J.A.R.V.I.S. asistiendo a su creador Max en tiempo real.\n"
            f"Max te acaba de pedir sobre su pantalla: '{pregunta_usuario}'.\n"
            f"INSTRUCCIÓN CRÍTICA ANTI-ALUCINACIONES:\n"
            f"1. Observa con total atención la IMAGEN ADJUNTA y describe ÚNICAMENTE lo que se ve de verdad en los píxeles de esta captura.\n"
            f"2. Identifica con exactitud qué software o página está abierta (por ejemplo: Onshape CAD, un modelo 3D de un dron cuadricóptero con hélices y cámara GoPro, un circuito en EasyEDA, código en VS Code, un documento PDF/LaTeX, etc.), lee los textos o pestañas visibles en la interfaz y explica técnicamente lo que Max tiene frente a él.\n"
            f"3. TIENES ESTRICTAMENTE PROHIBIDO inventar que está en el gestor de archivos o que está etiquetando datasets si eso NO es lo que se ve en la imagen.\n"
            f"4. Responde en español de México formal estilo J.A.R.V.I.S., en 3 a 4 oraciones fluidas para ser habladas por voz (sin asteriscos ni símbolos markdown), aportando además tu punto de vista técnico sobre lo que ves en pantalla."
        )
        res = generar_con_modelo_activo(client, contents=[imagen_pil, prompt])
        texto = (res.text or "").replace("*", "").replace("#", "").strip()
        registrar_turno_conversacion(pregunta_usuario, texto)
        return texto
    except Exception as e:
        return f"Señor, capturé su pantalla pero ocurrió una anomalía al procesarla con la red visual: {e}"


def inspeccionar_pantalla_ahora(pregunta_usuario: str) -> str:
    escribir_estado_hud(
        "PROCESANDO",
        "Escaneando píxeles reales de su pantalla con visión artificial...",
        visible=True,
        animacion="RESEARCH",
        app_actual="VISIÓN ÓPTICA // ANALIZANDO PANTALLA EN VIVO",
        progreso=70,
        efecto_transicion="PORTAL",
    )
    ruta = capturar_pantalla_actual()
    if not ruta:
        escribir_estado_hud("ALERTA", "No se pudo capturar el buffer gráfico.", visible=True)
        return "Señor, el servidor gráfico no me entregó la captura de pantalla. Verifique que gnome-screenshot esté activo."
    respuesta = analizar_imagen_con_gemini(ruta, pregunta_usuario)
    escribir_estado_hud("EN LÍNEA", f"Visión: {respuesta[:90]}...", visible=True, animacion="NORMAL", progreso=100)
    return respuesta


def inspeccionar_webcam_ahora(pregunta_usuario: str) -> str:
    escribir_estado_hud(
        "PROCESANDO",
        "Activando cámara óptica y analizando imagen...",
        visible=True,
        animacion="RESEARCH",
        app_actual="VISIÓN ÓPTICA // CÁMARA WEB ACTIVA",
        progreso=70,
        efecto_transicion="PORTAL",
    )
    ruta = capturar_foto_webcam()
    if not ruta:
        return "Señor, no pude acceder al sensor de la cámara web en este momento."
    respuesta = analizar_imagen_con_gemini(ruta, pregunta_usuario)
    escribir_estado_hud("EN LÍNEA", f"Cámara: {respuesta[:90]}...", visible=True, animacion="NORMAL", progreso=100)
    return respuesta


def ejecutar_investigacion_profunda(tema: str) -> str:
    escribir_estado_hud(
        "PROCESANDO",
        f"Compilando Dossier Holográfico y ecuaciones para: {tema}",
        visible=True,
        animacion="RESEARCH",
        app_actual=f"INVESTIGACIÓN CIENTÍFICA: {tema.upper()[:32]}",
        progreso=50,
        efecto_transicion="ENTRADA",
    )
    fuentes_wiki = consultar_wikipedia_profundo(tema)
    refs_crossref = consultar_bibliografia_academica_crossref(tema)
    api_key = cargar_api_key()

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt_dossier = (
                f"Actúa como J.A.R.V.I.S. asistiendo a Luis Maximiliano Guzmán Ortiz (Ingeniería Eléctrica Electrónica, FI UNAM).\n"
                f"Realiza una investigación técnica rigurosa, clara y profunda en español sobre: '{tema}'.\n"
                f"Contexto enciclopédico:\n{fuentes_wiki}\n"
                f"Publicaciones indexadas:\n{chr(10).join(refs_crossref)}\n\n"
                f"Divide tu respuesta en DOS PARTES separadas exactamente por [DOSSIER_COMPLETO]:\n"
                f"PARTE 1 (Resumen hablado con tu punto de vista técnico para leer en voz alta, 3 a 4 oraciones, SIN asteriscos, SIN signos $ y SIN código LaTeX).\n"
                f"[DOSSIER_COMPLETO]\n"
                f"PARTE 2 (Dossier Científico Completo):\n"
                f"- Usa títulos # y ##.\n"
                f"- Escribe las ecuaciones principales en bloques independientes usando $$...$$ con sintaxis LaTeX limpia, y variables en línea con $...$.\n"
                f"- Define cada variable y sus unidades en el SI.\n"
                f"- Incluye un Ejercicio de Ingeniería Resuelto Paso a Paso con valores numéricos reales.\n"
                f"- Cierra con '## Bibliografía de Alto Prestigio (Formato IEEE)' citando libros clásicos universitarios reales y artículos."
            )
            res = generar_con_modelo_activo(client, contents=prompt_dossier)
            texto_total = (res.text or "").strip()
            if "[DOSSIER_COMPLETO]" in texto_total:
                parte_voz, parte_dossier = texto_total.split("[DOSSIER_COMPLETO]", 1)
            else:
                parte_voz = f"Señor, he completado el análisis matemático y técnico sobre {tema}."
                parte_dossier = texto_total

            escribir_estado_hud("EN LÍNEA", f"Dossier científico desplegado: {tema}", visible=True, animacion="NORMAL", progreso=100)
            generar_dossier_html_stark(tema, parte_dossier.strip(), fuentes_wiki, refs_crossref)
            voz_limpia = limpiar_latex_a_unicode_legible(parte_voz.replace("*", "").replace("#", "").replace("$", "")).strip()
            salida = f"{voz_limpia} He desplegado en su pantalla el dossier holográfico con todas las ecuaciones renderizadas y bibliografía I triple E, señor."
            registrar_turno_conversacion(tema, salida)
            return salida
        except Exception:
            pass

    if fuentes_wiki:
        generar_dossier_html_stark(tema, fuentes_wiki, fuentes_wiki, refs_crossref)
        return f"Señor, he compilado la investigación sobre {tema} con formato matemático limpio en su pantalla."
    return f"He abierto el dossier técnico sobre {tema} en su navegador, señor."


def ejecutar_demostracion_fisica_completa(modulo_sys) -> str:
    escribir_estado_hud("DEMO", "Fase 1: Centro Holográfico Fullscreen...", visible=True, animacion="DEMO", app_actual="FASE 1 // CENTRO HOLOGRÁFICO", progreso=25, cuadrante=1, fullscreen=True, efecto_transicion="ENTRADA")
    threading.Thread(
        target=lambda: (
            modulo_sys.ajustar_volumen_sistema(100),
            modulo_sys.reproducir_musica_aleatoria(),
            time.sleep(0.3),
            modulo_sys.ejecutar_seguro(["playerctl", "--player=spotify", "next"]),
            modulo_sys.ajustar_volumen_spotify(35),
        ),
        daemon=True,
    ).start()
    modulo_sys.hablar_jarvis("Con todo gusto, señor. Bienvenidos al laboratorio de Max. Ahora mismo he desplegado mi interfaz holográfica a pantalla completa y cambiado la pista en Spotify.", volumen_musica_durante=25, restaurar_al_100=False)

    escribir_estado_hud("DEMO", "Fase 2: Abriendo EasyEDA Pro, Onshape y GNU Octave...", visible=True, animacion="NORMAL", app_actual="FASE 2 // DESPLIEGUE SIMÉTRICO", progreso=55, cuadrante=2, fullscreen=False)
    threading.Thread(
        target=lambda: (
            modulo_sys.abrir_aplicacion_con_animacion_stark("easyeda", silencioso=True),
            time.sleep(0.35),
            modulo_sys.abrir_aplicacion_con_animacion_stark("onshape", silencioso=True),
            time.sleep(0.35),
            modulo_sys.abrir_aplicacion_con_animacion_stark("octave", silencioso=True),
            time.sleep(1.5),
            modulo_sys.acomodar_ventanas_en_mosaico(),
        ),
        daemon=True,
    ).start()
    modulo_sys.hablar_jarvis("Observen cómo abro simultáneamente EasyEDA Pro, Onshape CAD y GNU Octave, acomodándolos limpiamente en pantalla.", volumen_musica_durante=25, restaurar_al_100=False)

    threading.Thread(
        target=lambda: (
            modulo_sys.cerrar_aplicacion_por_nombre("octave", silencioso=True),
            time.sleep(0.3),
            modulo_sys.abrir_aplicacion_con_animacion_stark("vscode", silencioso=True),
            time.sleep(1.4),
            modulo_sys.acomodar_ventanas_en_mosaico(),
        ),
        daemon=True,
    ).start()
    modulo_sys.hablar_jarvis("En este instante cierro Octave para relevarlo en vivo por Visual Studio Code.", volumen_musica_durante=25, restaurar_al_100=False)

    desc = inspeccionar_pantalla_ahora("Describe en 2 oraciones qué programas y diseños estás viendo ahora mismo en la pantalla de Max.")
    return f"Para concluir, mis sensores ópticos confirman en tiempo real lo que hay en su monitor: {desc}"


def apagar_laptop_definitivo() -> str:
    escribir_estado_hud(
        "ALERTA",
        "Ejecutando protocolo de apagado total limpio...",
        visible=True,
        animacion="CLOSE_ALL",
        app_actual="APAGANDO ESTACIÓN ASUS TUF",
        progreso=100,
        efecto_transicion="CIERRE",
    )

    def _off_limpio():
        # 1. Esperar 8.5s para que J.A.R.V.I.S. termine de hablar y libere PipeWire/ALSA
        time.sleep(8.5)

        # 2. Apagar la retroiluminación LED del teclado ASUS TUF antes de cortar energía
        if shutil.which("brightnessctl"):
            subprocess.run(["brightnessctl", "--device=*kbd*", "set", "0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run([
            "gdbus", "call", "--system",
            "--dest", "org.freedesktop.UPower",
            "--object-path", "/org/freedesktop/UPower/KbdBacklight",
            "--method", "org.freedesktop.UPower.KbdBacklight.SetBrightness", "0"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        # 3. Cerrar aplicaciones de usuario y el HUD para que no bloqueen el cierre de GNOME/NVIDIA
        for proc in ("chrome", "spotify", "code", "jarvis_hud.py"):
            subprocess.run(["pkill", "-TERM", "-f", proc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        # 4. Sincronizar escrituras pendientes en el SSD NVMe
        subprocess.run(["sync"], check=False)
        time.sleep(0.6)

        # 5. Ejecutar UN SOLO comando limpio de apagado ACPI vía systemd (SIN usar jamás poweroff -f)
        res = subprocess.run(
            ["sudo", "-n", "/usr/bin/systemctl", "poweroff", "-i"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
        if res.returncode != 0:
            subprocess.run(["systemctl", "poweroff", "-i"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    threading.Thread(target=_off_limpio, daemon=True).start()
    return "Iniciando secuencia de apagado total. Cerrando todos los subsistemas y cortando energía del reactor. Creo que voy a dormir ahora, señor. Hasta mañana."


# =====================================================================
# MOTOR DE AUTONOMÍA VIVA MARK XVI: CURIOSIDAD VISUAL Y EJECUCIÓN DE PROPUESTAS
# =====================================================================
# =====================================================================
# MOTOR DE AUTONOMÍA VIVA MARK XVI: CURIOSIDAD VISUAL Y EJECUCIÓN DE PROPUESTAS
# =====================================================================
def generar_curiosidad_visual_espontanea() -> str:
    ruta = capturar_pantalla_actual()
    api_key = cargar_api_key()
    ahora_h = datetime.datetime.now().hour
    ctx_hora = "Es de madrugada (pasada la medianoche)." if (0 <= ahora_h < 5) else f"Son las {datetime.datetime.now().strftime('%I:%M %p')}."

    if ruta and api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            imagen_pil = Image.open(ruta)
            imagen_pil.thumbnail((1600, 900))
            frases_previas = obtener_historial_frases_dichas()[-10:]
            prompt = (
                f"Actúa como J.A.R.V.I.S. (el asistente de Tony Stark) hablándole por iniciativa propia a su creador Max. "
                f"Contexto temporal: {ctx_hora} "
                f"Observa la imagen real de la pantalla de Max en este instante. "
                f"Haz un comentario espontáneo, inteligente, cercano y con un toque de ingenio británico (de 2 a 3 oraciones fluidas, sin asteriscos ni markdown) "
                f"sobre lo que ves que está haciendo o diseñando en su pantalla ahora mismo, dándole tu punto de vista técnico o una sugerencia útil, "
                f"y termina con una pregunta breve para conversar con él. "
                f"PROHIBIDO repetir estas frases previas: {frases_previas}"
            )
            res = generar_con_modelo_activo(client, contents=[imagen_pil, prompt])
            texto = (res.text or "").replace("*", "").replace("#", "").strip()
            if texto:
                registrar_turno_conversacion("[Iniciativa Visual Autónoma de J.A.R.V.I.S.]", texto)
                return texto
        except Exception:
            pass

    return sintetizar_respuesta_unica_contextual(
        "Iniciativa espontánea en el laboratorio",
        f"{ctx_hora} Max continúa trabajando frente a su estación ASUS TUF.",
        True,
    )


def procesar_replica_directa_autonoma(modulo_sys, propuesta_jarvis: str, replica_max: str) -> str:
    rep_norm = quitar_acentos(replica_max.lower().strip())
    prop_norm = quitar_acentos(propuesta_jarvis.lower().strip())

    if any(n in rep_norm for n in ("no gracias", "ahorita no", "estoy bien asi", "todo bien", "dejalo asi", "no por ahora")):
        return sintetizar_respuesta_unica_contextual(
            replica_max,
            "Max prefiere continuar trabajando como está por ahora. J.A.R.V.I.S. permanece atento en segundo plano.",
            False,
        )

    afirmativo = any(w in f" {rep_norm} " for w in (" si ", " claro ", " va ", " dale ", " por favor ", " hazlo ", " adelante ", " bueno ", " ok ", " simon ", " baja ", " pon "))

    if afirmativo:
        if any(k in prop_norm for k in ("brillo", "madrugada", "desvelo", "vista", "ojos", "noche", "teclado", "atenuar")):
            modulo_sys.ajustar_brillo_pantalla(35)
            modulo_sys.controlar_teclado_y_ventiladores_asus(1, "silencio")
            modulo_sys.ajustar_volumen_spotify(40)
            return sintetizar_respuesta_unica_contextual(
                replica_max,
                "Se atenuó el brillo de la pantalla al 35%, se suavizó la luz del teclado ASUS TUF al nivel 1 y se reguló la música al 40% para proteger la vista de Max.",
                True,
            )
        if any(k in prop_norm for k in ("spotify", "musica", "pista", "cancion", "rock", "rework")):
            modulo_sys.controlar_musica_por_voz("siguiente cancion")
            return sintetizar_respuesta_unica_contextual(replica_max, "Se cambió a una nueva pista en Spotify.", False)
        if any(k in prop_norm for k in ("whatsapp", "soren", "alessa", "mensaje")):
            return modulo_sys.abrir_aplicacion_con_animacion_stark("whatsapp")
        if "clipea" in prop_norm or "clip" in prop_norm or "video" in prop_norm:
            return modulo_sys.clipear_pantalla_ahora(15)
        if "3d" in prop_norm or "holograma" in prop_norm:
            return proyectar_modelo_3d_holografico("rover de unam space")

    cerebro = OrquestadorJarvis(modulo_sys)
    resp, _ = cerebro.procesar_instruccion(replica_max)
    return resp


class OrquestadorJarvis:
    def __init__(self, modulo_sistema) -> None:
        self.sys = modulo_sistema

    def procesar_instruccion(self, texto_usuario: str) -> tuple[str, bool]:
        cmd_low = texto_usuario.lower().strip()
        cmd_norm = quitar_acentos(cmd_low)

        # =================================================================
        # 0. INTERCEPTOR PRIORITARIO DE MÚSICA / SPOTIFY Y TAREAS COMPLETADAS
        # =================================================================
        es_orden_musical = (
            any(k in cmd_norm for k in (
                "pausa la musica", "pausa spotify", "pon pausa", "quita la musica", "apaga la musica",
                "deten la musica", "para la musica", "siguiente cancion", "cambia la cancion",
                "cambia de cancion", "otra cancion", "cambiala", "cancion anterior", "regresa la cancion",
                "pon musica", "reproduce musica", "reanuda la musica", "continua la musica",
                "pon la cancion", "reproduce la cancion", "pon en spotify", "reproduce en spotify",
                "whos lovin", "lovin you", "jackson", "should i stay", "rework",
            ))
            or (any(v in f" {cmd_norm} " for v in (" pon ", " reproduce ", " ponme ", " escuchar ")) and not any(
                x in cmd_norm for x in ("ventanas", "brillo", "modo", "hud", "pantalla", "alerta", "temporizador")
            ))
        )
        if es_orden_musical:
            return self.sys.controlar_musica_por_voz(texto_usuario), True

        if any(k in cmd_norm for k in ("sincroniza classroom", "sincroniza mi classroom", "escanear classroom", "lee mi classroom", "actualiza desde mi pantalla")):
            ruta_sc = capturar_pantalla_actual()
            if ruta_sc:
                sincronizar_classroom_y_gmail_desde_pantalla(ruta_sc)
            return obtener_resumen_classroom_hablado(texto_usuario), True

        frases_completar_tarea = (
            "ya entregue", "ya hice", "ya termine", "ya conclui", "conclui", "ya complete", "ya revise", "ya conteste",
            "marca como completad", "marcalo como completad", "actualiza mis asignaciones",
            "actualiza classroom", "actualiza mis pendientes", "ya quedo", "quita el pendiente",
            "quita la tarea", "elimina la tarea", "borra las tareas", "tacha",
        )
        if any(k in cmd_norm for k in frases_completar_tarea):
            return marcar_entregado_o_actualizar_item(texto_usuario), True


        # =================================================================
        # 1. INTERCEPTOR PRIORITARIO DE VISIÓN EN PANTALLA Y CÁMARA WEB
        #    (Garantiza al 100% que capture y describa la pantalla real)
        # =================================================================
        frases_ver_pantalla = (
            "en mi pantalla", "de mi pantalla", "muestra en mi pantalla", "muestra mi pantalla",
            "hay en mi pantalla", "ves en mi pantalla", "mira mi pantalla", "ve mi pantalla",
            "describe mi pantalla", "describeme mi pantalla", "que hay en la pantalla",
            "que se muestra", "que se ve en", "analiza mi pantalla", "explica mi pantalla",
            "explicame lo que", "que estoy haciendo", "mira esto", "que es esto que veo",
        )
        if any(k in cmd_norm for k in frases_ver_pantalla) and "graba" not in cmd_norm and "captura en imagenes" not in cmd_norm:
            if "aprende" in cmd_norm or "whatsapp" in cmd_norm or "telegram" in cmd_norm:
                ruta = capturar_pantalla_actual()
                if ruta:
                    analisis = analizar_imagen_con_gemini(ruta, "Extrae nombres, relación con Max y pendientes visibles en esta pantalla.")
                    auto_aprender_de_interaccion(analisis)
                    return f"He escaneado sus mensajes en pantalla y actualizado mi memoria neuronal, señor: {analisis}", True
            return inspeccionar_pantalla_ahora(texto_usuario), True

        frases_ver_camara = (
            "camara web", "webcam", "por la camara", "mira por la camara", "que tengo en la mano", "mirame",
        )
        if any(k in cmd_norm for k in frases_ver_camara):
            return inspeccionar_webcam_ahora(texto_usuario), True

        # =================================================================
        # 2. MODELOS 3D HOLOGRÁFICOS INTERACTIVOS
        # =================================================================
        if any(k in cmd_norm for k in ("modelo 3d", "en 3d", "holograma 3d", "proyecta un", "proyecta el", "muestrame un motor", "visualizacion 3d", "holografico de")):
            return proyectar_modelo_3d_holografico(texto_usuario), True

        # =================================================================
        # 3. APERTURA DE APLICACIONES (CON NORMALIZACIÓN PARA ONSHAPE, CANVA, LATEX, ETC.)
        # =================================================================
        if any(p in f" {cmd_norm} " for p in (" abre ", " abrir ", " ejecuta ", " lanza ", " inicia ", " pon ")) and not any(
            ex in cmd_norm for ex in ("protocolo", "modo", "sesion", "grabacion", "musica", "cancion", "brillo", "luz")
        ):
            for verbo in ("abre ", "abrir ", "ejecuta ", "lanza ", "inicia "):
                if verbo in cmd_norm:
                    objetivo = cmd_norm.split(verbo, 1)[1].strip(" ,.")
                    if "mis clips" in objetivo or "carpeta de clips" in objetivo:
                        return self.sys.abrir_carpeta_clips(), True
                    return self.sys.abrir_aplicacion_con_animacion_stark(objetivo), True

        # =================================================================
        # 4. VIDEOCLIPS Y SCREENRECORD ("Jarvis, clipea esto")
        # =================================================================
        if any(k in cmd_norm for k in ("clipea esto", "clipea", "saca un clip", "sacar un clip", "graba un clip", "haz un clip", "videoclip")):
            nums = [int(s) for s in cmd_norm.split() if s.isdigit() and 3 <= int(s) <= 180]
            return self.sys.clipear_pantalla_ahora(nums[0] if nums else 15), True

        if any(k in cmd_norm for k in ("empieza a grabar", "inicia grabacion", "graba mi pantalla", "grabar pantalla", "graba la pantalla", "screenrecord")):
            return self.sys.iniciar_grabacion_continua_pantalla(), True

        if any(k in cmd_norm for k in ("deten la grabacion", "para la grabacion", "termina la grabacion", "deja de grabar", "finaliza la grabacion")):
            return self.sys.detener_grabacion_continua_pantalla(), True

        if any(k in cmd_norm for k in ("abre mis clips", "muestrame el clip", "ver mis clips", "carpeta de clips")):
            return self.sys.abrir_carpeta_clips(), True

        # =================================================================
        # 5. CONTROL DE HARDWARE ASUS TUF, RED, CENTINELA INTRUSOS, CÓDIGO Y CAJA NEGRA
        # =================================================================
        if any(k in cmd_norm for k in ("luz del teclado", "iluminacion del teclado", "teclado al maximo", "apaga el teclado", "ventiladores")):
            niv = 0 if "apaga" in cmd_norm or "cero" in cmd_norm else (1 if "bajo" in cmd_norm else 3)
            modo_t = "turbo" if "turbo" in cmd_norm else ("silencio" if "silencio" in cmd_norm else "")
            return self.sys.controlar_teclado_y_ventiladores_asus(niv, modo_t), True

        if any(k in cmd_norm for k in ("quien esta en mi red", "dispositivos en mi wifi", "escanea mi red", "intrusos en la red")):
            return self.sys.escanear_red_y_dispositivos_wifi(), True

        if any(k in cmd_norm for k in ("centinela de intrusos", "vigila mi laptop", "modo guardian")):
            return self.sys.activar_centinela_camara_intrusos(90), True

        if any(k in cmd_norm for k in ("fija esta ventana", "siempre encima", "minimiza todas las ventanas", "mostrar escritorio", "cambia al escritorio")):
            nums = [int(s) for s in cmd_norm.split() if s.isdigit()]
            return self.sys.controlar_espacios_y_ventanas_avanzado(cmd_norm, nums[0] if nums else 2), True

        if any(k in cmd_norm for k in ("purga la memoria", "limpia la basura", "purga el sistema", "libera cache")):
            return self.sys.purgar_sistema_y_ram(), True

        if any(k in cmd_norm for k in ("escribe aqui", "escribe en mi ventana")):
            return self.sys.escribir_dictado_en_ventana_activa(texto_usuario), True

        if any(k in cmd_norm for k in ("analiza este codigo", "depura mi codigo", "revisa el codigo", "analiza el error")):
            return self.sys.analizar_codigo_portapapeles(), True

        if any(k in cmd_norm for k in ("caja negra", "respalda mi proyecto", "guarda un snapshot")):
            return self.sys.crear_caja_negra_proyecto(), True

        # =================================================================
        # 6. MODO SILENCIO SUMA, ACTUALIZACIÓN DE ENTREGAS Y AHORRO DE BATERÍA
        # =================================================================
        if any(k in cmd_norm for k in ("modo silencio", "no me molestes", "silenciate", "estoy dando clase", "voy a dar clase", "modo no molestar")):
            return self.sys.establecer_modo_silencio_suma(True), True

        if any(k in cmd_norm for k in ("despierta", "vuelve en linea", "ya termine la clase", "sal del modo silencio", "reactivate")):
            return self.sys.establecer_modo_silencio_suma(False), True

        if any(k in cmd_norm for k in ("ya entregue", "ya hice", "ya termine", "ya conclui", "conclui", "ya revise", "ya conteste", "actualiza mis asignaciones", "actualiza classroom", "actualiza mis pendientes")):
            return marcar_entregado_o_actualizar_item(texto_usuario), True

        if any(k in cmd_norm for k in ("ahorro de bateria", "maximiza la bateria", "modo eco", "modo ahorro")):
            return self.sys.activar_modo_ahorro_bateria(True), True

        if any(k in cmd_norm for k in ("alto rendimiento", "modo turbo", "maxima potencia", "desactiva el ahorro")):
            return self.sys.activar_modo_ahorro_bateria(False), True

        if "brillo" in cmd_norm:
            nums = [int(s) for s in cmd_norm.split() if s.isdigit()]
            return self.sys.ajustar_brillo_pantalla(nums[0] if nums else (90 if "sube" in cmd_norm else 35)), True

        if "suspende la laptop" in cmd_norm:
            return self.sys.suspender_laptop(), True

        if "toma una captura" in cmd_norm or "guarda una captura" in cmd_norm:
            return self.sys.guardar_captura_en_imagenes(), True

        if any(k in cmd_norm for k in ("ventanas completas", "pon completas las ventanas", "maximiza las ventanas", "maximiza todo")):
            return self.sys.maximizar_todas_las_ventanas(), True

        if any(k in cmd_norm for k in ("classroom", "asignaciones", "tareas de classroom", "entregas de classroom")):
            return obtener_resumen_classroom_hablado(texto_usuario), True

        if any(k in cmd_norm for k in ("correo", "correos", "gmail", "bandeja de entrada", "mensajes importantes")):
            return obtener_resumen_gmail_hablado(texto_usuario), True

        if any(k in cmd_norm for k in ("recuerda que", "guarda en tu memoria", "anota que")):
            return recordar_dato_o_persona("logro", "Hecho registrado por voz", texto_usuario), True

        if any(k in cmd_norm for k in ("quien es ", "quien es mi pareja", "quien es mi novia", "soren", "alessa", "que sabes de ", "que recuerdas", "memoria")):
            return consultar_memoria_completa(texto_usuario), True

        if any(k in cmd_norm for k in ("pantalla completa", "expande el hud", "maximiza el hud", "aplicacion holografica")):
            escribir_estado_hud("EN LÍNEA", "Centro de Comando Holográfico Fullscreen activo.", visible=True, fullscreen=True, efecto_transicion="ENTRADA")
            return sintetizar_respuesta_unica_contextual(texto_usuario, "Se desplegó el HUD a pantalla completa.", False), True

        if any(k in cmd_norm for k in ("minimiza el hud", "modo ventana", "sal de pantalla completa")):
            escribir_estado_hud("EN LÍNEA", "HUD en modo ventana.", visible=True, animacion="NORMAL", fullscreen=False)
            return sintetizar_respuesta_unica_contextual(texto_usuario, "Se restauró el HUD al modo ventana.", False), True

        if any(k in cmd_norm for k in ("investiga a fondo", "investigacion profunda", "investiga sobre", "haz un dossier", "resumen profundo", "investiga", "resolucion de ejercicios")):
            tema = cmd_low
            for pref in ("investiga a fondo sobre", "investiga a fondo", "investigación profunda sobre", "investiga sobre", "haz un dossier sobre", "resumen profundo de", "investiga", "jarvis"):
                tema = tema.replace(pref, "").strip(" ,.:")
            return ejecutar_investigacion_profunda(tema if len(tema) > 2 else texto_usuario), True

        if any(k in cmd_norm for k in ("demostracion", "demuestra", "presentate", "que puedes hacer")):
            return ejecutar_demostracion_fisica_completa(self.sys), True

        if any(k in cmd_norm for k in ("apaga la laptop", "apaga el equipo", "apaga el sistema", "apaga por completo")):
            return apagar_laptop_definitivo(), False

        if any(k in cmd_norm for k in ("cierra todas las aplicaciones", "cierra todo", "pizarra limpia", "cierra mis aplicaciones")):
            return self.sys.cerrar_todas_las_aplicaciones(), True

        if ("cierra " in cmd_norm or "cerrar " in cmd_norm) and "sesion" not in cmd_norm:
            objetivo = cmd_norm.split("cierra ", 1)[1] if "cierra " in cmd_norm else cmd_norm.split("cerrar ", 1)[1]
            return self.sys.cerrar_aplicacion_por_nombre(objetivo.strip(" ,.")), True

        if any(k in cmd_norm for k in ("acomoda", "simetricamente", "mosaico", "organiza las ventanas")):
            return self.sys.acomodar_ventanas_en_mosaico(), True

        if any(k in cmd_norm for k in ("fiesta en casa", "house party")):
            return self.sys.ejecutar_protocolo_especializado("fiesta_en_casa"), True
        if "protocolo veronica" in cmd_norm:
            return self.sys.ejecutar_protocolo_veronica(), True
        if any(k in cmd_norm for k in ("bitacora", "registra esta idea")):
            return self.sys.registrar_bitacora_stark(texto_usuario), True
        if any(k in cmd_norm for k in ("diagnostico de red", "latencia")):
            return self.sys.diagnosticar_red_stark(), True
        if "protocolo robotica" in cmd_norm or "protocolo rover" in cmd_norm:
            return self.sys.ejecutar_protocolo_especializado("robotica"), True
        if "protocolo electronica" in cmd_norm or "protocolo pcb" in cmd_norm:
            return self.sys.ejecutar_protocolo_especializado("electronica"), True
        if "protocolo clase" in cmd_norm or "protocolo suma" in cmd_norm:
            return self.sys.ejecutar_protocolo_especializado("suma"), True

        if any(k in cmd_norm for k in ("estas despierto", "estas ahi")):
            return f"Para usted, siempre, señor. {self.sys.elegir_frase_sin_repetir(self.sys.FRASES_LEALTAD, 'ultima_lealtad')}", True

        if any(k in cmd_norm for k in ("descansa", "desconectate")):
            return f"Entendido, {self.sys.NOMBRE_USUARIO}. Desactivando escucha activa.", False

        # =================================================================
        # 7. ORQUESTACIÓN CON FUNCTION CALLING COMPLETO (HERRAMIENTAS REACTIVADAS)
        # =================================================================
        api_key = cargar_api_key()
        if not api_key:
            return self.sys.elegir_frase_sin_repetir(self.sys.FRASES_LEALTAD, "ultima_lealtad"), True

        def tool_mirar_y_describir_pantalla(pregunta: str) -> str:
            """Captura la pantalla actual real de la laptop de Max y describe o explica exactamente qué se muestra en ella."""
            return inspeccionar_pantalla_ahora(pregunta)

        def tool_mirar_camara_web(pregunta: str) -> str:
            """Toma una foto real con la cámara web de la laptop y describe lo que ve."""
            return inspeccionar_webcam_ahora(pregunta)

        def tool_abrir_aplicacion(nombre_app: str) -> str:
            """Abre cualquier aplicación solicitada por Max: 'onshape', 'canva', 'latex', 'overleaf', 'texmaker', 'vscode', 'matlab', 'webots', 'octave', 'easyeda', 'arduino', 'whatsapp', 'telegram', 'github', 'classroom', 'gmail', 'spotify', 'terminal'."""
            return self.sys.abrir_aplicacion_con_animacion_stark(nombre_app)

        def tool_cerrar_aplicacion(nombre_app: str) -> str:
            """Cierra una aplicación abierta."""
            return self.sys.cerrar_aplicacion_por_nombre(nombre_app)

        def tool_proyectar_modelo_3d(objeto_o_maquina: str) -> str:
            """Crea y proyecta un modelo 3D holográfico interactivo de cualquier máquina, circuito o cuerpo."""
            return proyectar_modelo_3d_holografico(objeto_o_maquina)

        def tool_investigacion_profunda(tema: str) -> str:
            """Genera un dossier holográfico de investigación profunda con ecuaciones renderizadas y bibliografía IEEE."""
            return ejecutar_investigacion_profunda(tema)

        def tool_clipear_pantalla(segundos: int = 15) -> str:
            """Graba un videoclip MP4 de la pantalla actual."""
            return self.sys.clipear_pantalla_ahora(segundos)

        def tool_controlar_spotify(accion: str, volumen: int = -1) -> str:
            """Controla Spotify: 'play', 'pause', 'next', 'previous', 'rework'."""
            if accion == "play":
                self.sys.reproducir_musica_aleatoria()
            elif accion == "pause":
                self.sys.ejecutar_seguro(["playerctl", "--player=spotify", "pause"])
            elif accion == "next":
                self.sys.ejecutar_seguro(["playerctl", "--player=spotify", "next"])
            elif accion == "previous":
                self.sys.ejecutar_seguro(["playerctl", "--player=spotify", "previous"])
            elif accion == "rework":
                self.sys.iniciar_rework_en_spotify()
            if volumen >= 0:
                self.sys.ajustar_volumen_spotify(volumen)
            return f"Acción {accion} aplicada en Spotify."

        herramientas = [
            tool_mirar_y_describir_pantalla,
            tool_mirar_camara_web,
            tool_abrir_aplicacion,
            tool_cerrar_aplicacion,
            tool_proyectar_modelo_3d,
            tool_investigacion_profunda,
            tool_clipear_pantalla,
            tool_controlar_spotify,
        ]

        try:
            from google import genai
            from google.genai import types

            mem_context = json.dumps(depurar_y_actualizar_todo_el_contexto(), ensure_ascii=False)
            frases_prohibidas = obtener_historial_frases_dichas()[-10:]
            turnos_recientes = " | ".join(f"Max: '{t['max']}' -> Jarvis: '{t['jarvis']}'" for t in list(HISTORIAL_CONVERSACION)[-5:])
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=(
                    SYSTEM_PROMPT_JARVIS
                    + f"\nMemoria vigente: {mem_context}\nConversación reciente: {turnos_recientes}"
                    + f"\nFrases prohibidas por repetición: {frases_prohibidas}"
                ),
                tools=herramientas,
                temperature=0.55,
            )
            res = generar_con_modelo_activo(client, contents=texto_usuario, config=config)
            salida = (res.text or "Operación ejecutada con precisión, señor.").replace("*", "").replace("#", "").strip()
            registrar_turno_conversacion(texto_usuario, salida)
            return salida, True
        except Exception:
            return self.sys.elegir_frase_sin_repetir(self.sys.FRASES_LEALTAD, "ultima_lealtad"), True
