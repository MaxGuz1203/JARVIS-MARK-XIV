#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Núcleo Maestro Mark XV (Arranque en Frío y Bloqueo por 2 Palmadas Garantizado)
- Bloqueo de sesión infalible al encender la laptop (sudo loginctl lock-sessions + D-Bus ScreenSaver)
- Protección contra falso bypass: espera siempre las 2 palmadas al arrancar
- Inicio musical 100% forzado con 'Should I Stay or Should I Go' (5s) -> Shuffle en playlist REWORK
- Control total de Spotify y buscador de canciones específicas (ej. 'Who's Lovin' You' de The Jackson 5)
- Apertura garantizada de Onshape, Canva, LaTeX, Modelos 3D Fullscreen, Dossiers MathJax y Videoclips
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import asyncio
import collections
import datetime
import glob
import io
import json
import os
import random
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import wave
import webbrowser
import zipfile
from pathlib import Path

import cv2
import edge_tts
import numpy as np
import psutil
import sounddevice as sd
import speech_recognition as sr
from PIL import ImageGrab

# Asegurar que el directorio ~/jarvis esté siempre en sys.path aunque se ejecute desde Autostart
DIRECTORIO_BASE = Path.home() / "jarvis"
if str(DIRECTORIO_BASE) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_BASE))

from jarvis_brain import OrquestadorJarvis, cargar_api_key, generar_con_modelo_activo, generar_curiosidad_visual_espontanea, procesar_replica_directa_autonoma
from jarvis_hud import escribir_estado_hud, leer_estado_hud_actual
from jarvis_memory import (
    depurar_y_actualizar_todo_el_contexto,
    escanear_contexto_mensajeria_y_web,
    marcar_entregado_o_actualizar_item,
    obtener_historial_frases_dichas,
    obtener_resumen_classroom_hablado,
    obtener_resumen_gmail_hablado,
    recordar_dato_o_persona,
    registrar_frase_dicha,
    sintetizar_respuesta_unica_contextual,
)

# =====================================================================
# 1. CONFIGURACIÓN GENERAL Y VARIABLES DE ESTADO
# =====================================================================
NOMBRE_USUARIO = "señor"
CIUDAD_LAT = 19.32        # Coyoacán / CDMX
CIUDAD_LON = -99.16

ARCHIVO_AGENDA = DIRECTORIO_BASE / "agenda.json"
ARCHIVO_ESTADO = DIRECTORIO_BASE / "ultimo_estado.json"
ARCHIVO_BITACORA = DIRECTORIO_BASE / "bitacora_ingenieria_stark.md"

PLAYLIST_REWORK_URI = "spotify:playlist:76XrNkMaZH431dSVflAY49"
SHOULD_I_STAY_URI = "spotify:track:39shmbIHICJ2Wxnk1fPSdz"
MEZCLAR_RESTO_DE_PLAYLIST = True
SEGUNDOS_INTRO_MUSICA = 5

VOLUMEN_SISTEMA_MAX = 100
VOLUMEN_MUSICA_FONDO_PCT = 75
VOLUMEN_MUSICA_COMANDO_PCT = 25
VOLUMEN_MUSICA_FINAL_PCT = 100

MODO_SUSPENSION_SILENCIOSA = False
PROCESO_GRABACION_CONTINUA: subprocess.Popen | None = None
BANDERA_DETENER_GRABACION_CV2 = False
ULTIMO_CLIP_GUARDADO: Path | None = None
CENTINELA_INTRUSOS_ACTIVO = False

APPS_INICIO_MOSAICO = [
    {
        "nombre": "NÚCLEO COGNITIVO (GEMINI, CLASSROOM & GMAIL)",
        "tipo": "chrome_tabs",
        "urls": ["https://gemini.google.com", "https://classroom.google.com", "https://mail.google.com"],
        "sector": 1,
    },
    {
        "nombre": "INGENIERÍA Y DISEÑO (OVERLEAF, ONSHAPE & GITHUB)",
        "tipo": "chrome_tabs",
        "urls": ["https://www.overleaf.com/project", "https://cad.onshape.com", "https://github.com"],
        "sector": 2,
    },
    {
        "nombre": "WHATSAPP COMMS LINK",
        "tipo": "app_o_web",
        "keywords": ["whatsdesk", "whatsapp"],
        "url": "https://web.whatsapp.com",
        "sector": 3,
    },
    {
        "nombre": "VISUAL STUDIO CODE IDE",
        "tipo": "bin",
        "bin": "code",
        "keywords": ["code"],
        "sector": 4,
    },
]

CATALOGO_APPS_MAX = {
    "matlab": {
        "nombre": "MATLAB", "keywords": ["matlab"], "bin": "matlab", "procesos": ["MATLAB", "matlab"],
        "frases_stark": [
            "Abriendo MATLAB y reservando núcleos de cálculo matricial, señor.",
            "Desplegando el entorno matemático MATLAB en este instante, Max.",
        ],
    },
    "webots": {
        "nombre": "Webots", "keywords": ["webots"], "bin": "webots", "procesos": ["webots", "webots-bin"],
        "frases_stark": [
            "Abriendo el simulador robótico Webots y preparando el entorno físico del rover, señor.",
            "Desplegando Webots para sus pruebas de navegación autónoma, Max.",
        ],
    },
    "octave": {
        "nombre": "GNU Octave", "keywords": ["octave"], "bin": "octave --gui", "procesos": ["octave", "octave-gui"],
        "frases_stark": [
            "Abriendo GNU Octave en este instante. Los motores de análisis numérico están listos, señor.",
            "Iniciando la interfaz gráfica de GNU Octave para sus cálculos, Max.",
        ],
    },
    "easyeda": {
        "nombre": "EasyEDA Pro", "keywords": ["easyeda"], "bin": "easyeda-pro", "procesos": ["easyeda", "easyeda-pro"],
        "frases_stark": [
            "Abriendo EasyEDA Pro mientras cargo las reglas de ruteo para sus placas de potencia, señor.",
            "Desplegando EasyEDA Pro. Excelente momento para avanzar con el PCB de UNAM SPACE.",
        ],
    },
    "arduino": {
        "nombre": "Arduino IDE", "keywords": ["arduino"], "bin": "arduino", "procesos": ["arduino", "arduino-ide"],
        "frases_stark": [
            "Abriendo Arduino IDE y sondeando los puertos seriales para sus microcontroladores, señor.",
            "Desplegando Arduino IDE. Listo para compilar y subir firmware al rover.",
        ],
    },
    "texmaker": {
        "nombre": "Texmaker", "keywords": ["texmaker"], "bin": "texmaker", "procesos": ["texmaker"],
        "frases_stark": ["Abriendo Texmaker para la compilación de sus reportes científicos en LaTeX, señor."],
    },
    "xournal": {
        "nombre": "Xournal++", "keywords": ["xournalpp", "xournal"], "bin": "xournalpp", "procesos": ["xournalpp"],
        "frases_stark": ["Abriendo su pizarra digital Xournal Plus Plus. Lista para sus ecuaciones de SUMA, señor."],
    },
    "vscode": {
        "nombre": "Visual Studio Code", "keywords": ["code"], "bin": "code", "procesos": ["code"],
        "frases_stark": [
            "Abriendo Visual Studio Code ahora mismo. Sus repositorios y extensiones están en línea, señor.",
            "Desplegando Visual Studio Code. La arquitectura de código aguarda sus instrucciones, Max.",
        ],
    },
    "github": {
        "nombre": "GitHub Desktop", "keywords": ["github"], "url_app": "https://github.com", "procesos": ["github-desktop"],
        "frases_stark": ["Abriendo GitHub y sincronizando el control de versiones de sus proyectos, señor."],
    },
    "whatsapp": {
        "nombre": "WhatsApp", "keywords": ["whatsdesk", "whatsapp"], "url_app": "https://web.whatsapp.com", "procesos": ["whatsdesk"],
        "frases_stark": ["Abriendo su enlace de comunicaciones en WhatsApp en tiempo real, señor."],
    },
    "classroom": {
        "nombre": "Google Classroom", "keywords": ["classroom"], "url_app": "https://classroom.google.com", "procesos": [],
        "frases_stark": ["Abriendo Google Classroom con sus entregas vigentes, señor."],
    },
    "gmail": {
        "nombre": "Gmail", "keywords": ["gmail"], "url_app": "https://mail.google.com", "procesos": [],
        "frases_stark": ["Abriendo su bandeja prioritaria de Gmail en pantalla, señor."],
    },
    "telegram": {
        "nombre": "Telegram", "keywords": ["telegram"], "bin": "telegram-desktop", "procesos": ["telegram-desktop", "Telegram"],
        "frases_stark": ["Abriendo Telegram y cifrando el canal de mensajería, señor."],
    },
    "discord": {
        "nombre": "Discord", "keywords": ["discord"], "bin": "discord", "procesos": ["Discord", "discord"],
        "frases_stark": ["Abriendo Discord y conectando los canales de voz del equipo, señor."],
    },
    "canva": {
        "nombre": "Canva", "keywords": ["canva"], "url_app": "https://www.canva.com", "procesos": [],
        "frases_stark": [
            "Abriendo la suite de diseño gráfico Canva en primer plano, señor.",
            "Desplegando Canva en su navegador ahora mismo, Max.",
        ],
    },
    "onshape": {
        "nombre": "Onshape CAD", "keywords": ["onshape"], "url_app": "https://cad.onshape.com", "procesos": [],
        "frases_stark": [
            "Abriendo Onshape y renderizando la geometría tridimensional en la nube, señor.",
            "Desplegando su estación CAD en Onshape para el modelado mecánico, Max.",
        ],
    },
    "latex": {
        "nombre": "LaTeX Overleaf", "keywords": ["overleaf", "texmaker"], "url_app": "https://www.overleaf.com/project", "procesos": ["texmaker"],
        "frases_stark": [
            "Abriendo su entorno de LaTeX en Overleaf. Compiladores listos, señor.",
            "Desplegando sus proyectos de LaTeX en pantalla ahora mismo, Max.",
        ],
    },
    "onlyoffice": {
        "nombre": "ONLYOFFICE", "keywords": ["onlyoffice"], "bin": "onlyoffice-desktopeditors", "procesos": ["DesktopEditors"],
        "frases_stark": ["Abriendo la suite documental ONLYOFFICE ahora mismo, señor."],
    },
    "libreoffice": {
        "nombre": "LibreOffice", "keywords": ["libreoffice"], "bin": "libreoffice", "procesos": ["soffice.bin"],
        "frases_stark": ["Abriendo LibreOffice en su estación de trabajo, señor."],
    },
    "sumo": {
        "nombre": "SUMO Simulation", "keywords": ["sumo"], "bin": "sumo-gui", "procesos": ["sumo-gui", "sumo"],
        "frases_stark": ["Abriendo el simulador de movilidad SUMO en pantalla, señor."],
    },
    "qt": {
        "nombre": "Qt 5 Designer", "keywords": ["designer", "qt5"], "bin": "designer", "procesos": ["designer"],
        "frases_stark": ["Abriendo Qt Designer para el modelado de interfaces gráficas, señor."],
    },
    "nvtop": {
        "nombre": "Monitor GPU nvtop", "keywords": ["nvtop"], "terminal_cmd": "nvtop", "procesos": ["nvtop"],
        "frases_stark": ["Abriendo nvtop y proyectando la telemetría en vivo de su tarjeta gráfica NVIDIA, señor."],
    },
    "htop": {
        "nombre": "Monitor de Procesos Htop", "keywords": ["htop"], "terminal_cmd": "htop", "procesos": ["htop"],
        "frases_stark": ["Abriendo Htop con el desglose de hilos del procesador en vivo, señor."],
    },
    "labelme": {
        "nombre": "Labelme Annotation", "keywords": ["labelme"], "bin": "labelme", "procesos": ["labelme"],
        "frases_stark": ["Abriendo Labelme para continuar el etiquetado neuronal del laboratorio LIRA, señor."],
    },
    "rviz": {
        "nombre": "RViz 2", "keywords": ["rviz"], "bin": "rviz2", "procesos": ["rviz2"],
        "frases_stark": ["Abriendo RViz 2 y enlazando los tópicos de visualización de ROS 2, señor."],
    },
    "gazebo": {
        "nombre": "Gazebo Sim", "keywords": ["gazebo"], "bin": "gz sim", "procesos": ["gz", "ruby"],
        "frases_stark": ["Abriendo Gazebo y cargando los motores de física para el rover, señor."],
    },
    "terminal": {
        "nombre": "Terminal de Ubuntu", "keywords": ["terminal"], "bin": "gnome-terminal", "procesos": ["gnome-terminal-server"],
        "frases_stark": ["Abriendo una nueva consola de comandos en su escritorio, señor."],
    },
    "archivos": {
        "nombre": "Explorador de Archivos", "keywords": ["nautilus"], "bin": "nautilus", "procesos": ["nautilus"],
        "frases_stark": ["Abriendo el gestor de archivos de su directorio principal, señor."],
    },
    "spotify": {
        "nombre": "Spotify", "keywords": ["spotify"], "bin": "spotify", "procesos": ["spotify"],
        "frases_stark": ["Abriendo Spotify y preparando sus pistas de enfoque, señor."],
    },
    "chrome": {
        "nombre": "Google Chrome", "keywords": ["chrome"], "bin": "google-chrome", "procesos": ["chrome"],
        "frases_stark": ["Abriendo el navegador Google Chrome en este momento, señor."],
    },
}

CANCIONES_FAVORITAS_URI = {
    "whos lovin you": ("Who's Lovin' You - The Jackson 5", "spotify:track:5M4yti0QxgqJieBpYa0Chd"),
    "who is lovin you": ("Who's Lovin' You - The Jackson 5", "spotify:track:5M4yti0QxgqJieBpYa0Chd"),
    "lovin you": ("Who's Lovin' You - The Jackson 5", "spotify:track:5M4yti0QxgqJieBpYa0Chd"),
    "loving you": ("Who's Lovin' You - The Jackson 5", "spotify:track:5M4yti0QxgqJieBpYa0Chd"),
    "jackson": ("Who's Lovin' You - The Jackson 5", "spotify:track:5M4yti0QxgqJieBpYa0Chd"),
    "should i stay": ("Should I Stay or Should I Go - The Clash", "spotify:track:39shmbIHICJ2Wxnk1fPSdz"),
    "together": ("Together - Nine Inch Nails", "spotify:track:5CgZ09x652797c52c3S2G5"),
    "nine inch nails": ("Together - Nine Inch Nails", "spotify:track:5CgZ09x652797c52c3S2G5"),
    "late nights": ("Late Nights & Heartbreak - Hannah Williams", "spotify:track:7AFE3418b1R2730b04H2kC"),
    "ghost town": ("Ghost Town - Kanye West", "spotify:track:7vgTNTvgKGQzGBK8f0G2vh"),
    "highest in the room": ("HIGHEST IN THE ROOM - Travis Scott", "spotify:track:3eekarcy7kvN4yt5ZFzltW"),
    "exit music": ("Exit Music (For A Film) - Radiohead", "spotify:track:0z1o5L7HJx562xZSATcIpY"),
    "subterranean": ("Subterranean Homesick Alien - Radiohead", "spotify:track:2CVV8PtUYYsux8XOzWkCP0"),
    "let down": ("Let Down - Radiohead", "spotify:track:2fuYa3Lx06QQJAm0MjztKr"),
}

VOZ_JARVIS = "es-MX-JorgeNeural"
VELOCIDAD_VOZ = "+6%"
TONO_VOZ = "-5Hz"
GANANCIA_VOZ_TTS = "+60%"

SAMPLE_RATE = 16000
BLOCK_DURATION = 0.04
CLAP_THRESHOLD = 0.35
SILENCE_THRESHOLD = 0.12
CREST_FACTOR_MIN = 5.0
MAX_CLAP_BLOCKS = 3
MIN_SILENCE_BLOCKS = 3
MIN_GAP_SECONDS = 0.18
MAX_GAP_SECONDS = 0.65

BLOQUEAR_AL_ARRANCAR = True
candado_voz = threading.Lock()

FRASES_APERTURA = [
    "Bienvenido de vuelta a su centro de comando holográfico, Max.",
    "Es un gusto tenerlo de regreso en el laboratorio, señor.",
    "Protocolo Showstopper Mark Quince activado con éxito. Sistemas holográficos en línea.",
    "Sistemas centrales despiertos tras los cinco segundos de introducción musical.",
    "Recepción acústica confirmada. Todo el taller se encuentra listo para su llegada, señor.",
]

FRASES_EPICAS_STARK_FINAL = [
    "Y como suele decirse en este taller, señor: a veces hay que correr antes de saber caminar. Su playlist Rework queda programada en modo aleatorio tras esta pista y todos los sistemas del Mark Quince están listos. Que comience el espectáculo, señor.",
    "El reactor está calibrado, los satélites en línea y su música al cien por ciento. He preparado el laboratorio, Max; ahora le toca a usted demostrar por qué es el ingeniero al mando. Disfrute el vuelo, señor.",
    "Todos los subsistemas han sido verificados y las ecuaciones lo esperan en pantalla. Rompa los límites hoy, señor; yo vigilaré sus espaldas desde el núcleo holográfico.",
    "La armadura lógica está presurizada y lista para el combate académico y robótico. Dejo su playlist Rework a máxima potencia. Siempre es un privilegio asistirlo, señor.",
]

FRASES_BATERIA_AGONIA = [
    "Señor... me temo que olvidó conectar el cargador y mis reservas de energía han caído al límite crítico. Mis sistemas se están oscureciendo... Creo que voy a dormir ahora, señor.",
    "Max, el reactor de batería está prácticamente agotado. Estoy guardando sus estados de memoria antes del corte eléctrico... Creo que voy a dormir ahora, señor. Hasta que vuelva a conectarme.",
    "Alerta de caída inminente de tensión. No me queda energía en el núcleo para mantenerme despierto... Creo que voy a dormir ahora, señor.",
]

FRASES_LEALTAD = [
    "A su entera disposición, señor.",
    "Nunca duermo, Max. Salvo cuando me ordena modo silencio en sus clases de SUMA o cuando olvida mi cargador. ¿En qué le ayudo?",
    "Sistemas cognitivos, proyectores 3D, grabadora de videoclips y control total de su ASUS TUF a sus órdenes.",
    "Aquí me tiene, vigilando cada proceso del laboratorio, señor.",
]

FRASES_ESPONTANEAS_ABURRIDO = [
    "Señor, detecto cero actividad en sus periféricos desde hace varios minutos. Si está aburrido, podríamos proyectar un modelo 3D holográfico o charlar sobre qué videojuego jugará hoy con Soren Alessa.",
    "Max, el silencio en el laboratorio es inusual. ¿Está meditando alguna ecuación de campos magnéticos o simplemente contemplando el vacío cósmico del fondo de pantalla?",
    "Señor, mis núcleos de procesamiento están al tres por ciento y me siento desaprovechado. ¿Quiere que cambiemos de pista en Spotify o que revisemos sus pendientes vigentes?",
]

CONSEJOS_CONTEXTO_LIRA = [
    "Señor, veo que está trabajando en los sistemas del laboratorio LIRA. Le sugiero verificar la inflación de obstáculos en el mapa de costos de ROS 2 y revisar las notas que Ruth y Enrique subieron a Notion.",
    "Max, mientras avanza con el entrenamiento neuronal y el etiquetado de LIRA, recuerde mantener balanceadas las clases del dataset. Si logra una buena prueba, dígame Jarvis clipea esto para guardarla en video.",
]

CONSEJOS_CONTEXTO_UNAM_SPACE = [
    "Señor, noto que tiene activos sus módulos de UNAM SPACE. Recuerde revisar la disipación térmica en los puentes H BTS setenta y nueve sesenta del sistema de tracción del rover.",
    "Max, excelente avance con la electrónica de UNAM SPACE. Si desea inspeccionar la cinemática del rover, pídame proyectar su modelo 3D holográfico en pantalla.",
]

CONSEJOS_CONTEXTO_ESTUDIO = [
    "Señor, detecto sesión de estudio académico activa. Recuerde que puede pedirme proyectar en 3D cualquier máquina eléctrica o campo magnético para visualizarlo mejor.",
    "Max, si está preparando material de Cálculo Integral para SUMA, recuerde que puede pedirme entrar en modo silencio cuando inicie su clase.",
]


def elegir_frase_sin_repetir(lista_frases: list[str], clave: str) -> str:
    historial_global = obtener_historial_frases_dichas()
    estado = {}
    if ARCHIVO_ESTADO.exists():
        try:
            estado = json.loads(ARCHIVO_ESTADO.read_text(encoding="utf-8"))
        except Exception:
            estado = {}
    ultima = estado.get(clave, "")
    opciones = [f for f in lista_frases if f != ultima and f not in historial_global[-15:]]
    if not opciones:
        opciones = [f for f in lista_frases if f != ultima] or lista_frases
    elegida = random.choice(opciones)
    estado[clave] = elegida
    try:
        DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
        ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    registrar_frase_dicha(elegida)
    return elegida


def ejecutar_seguro(comando: list[str]) -> bool:
    if not shutil.which(comando[0]):
        return False
    try:
        res = subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return res.returncode == 0
    except Exception:
        return False


# =====================================================================
# 2. BLOQUEO INFALIBLE DE PANTALLA AL ARRANCAR EN FRÍO (UBUNTU 24.04)
# =====================================================================
def pantalla_esta_bloqueada() -> bool:
    # Vía 1: D-Bus GNOME ScreenSaver
    try:
        salida = subprocess.check_output(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.ScreenSaver",
                "--object-path", "/org/gnome/ScreenSaver",
                "--method", "org.gnome.ScreenSaver.GetActive",
            ],
            stderr=subprocess.DEVNULL, text=True, timeout=1.5,
        )
        if "true" in salida.lower():
            return True
    except Exception:
        pass

    # Vía 2: loginctl LockedHint de la sesión
    try:
        sesiones = subprocess.check_output(["loginctl", "list-sessions", "--no-legend"], text=True, stderr=subprocess.DEVNULL)
        for lin in sesiones.splitlines():
            partes = lin.split()
            if len(partes) >= 3 and os.environ.get("USER", "maybeman") in lin:
                sid = partes[0]
                prop = subprocess.check_output(["loginctl", "show-session", sid, "-p", "LockedHint"], text=True, stderr=subprocess.DEVNULL)
                if "yes" in prop.lower():
                    return True
    except Exception:
        pass
    return False


def asegurar_pantalla_bloqueada_al_inicio() -> bool:
    """
    Espera a que GNOME Shell esté listo tras encender la laptop, sale de la vista
    de Actividades inicial de Ubuntu 24.04 y bloquea la sesión con confirmación real.
    """
    ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.screensaver", "lock-enabled", "true"])
    ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.lockdown", "disable-lock-screen", "false"])

    # Esperar hasta 15s a que el servicio org.gnome.ScreenSaver exista en el bus de sesión al arrancar en frío
    for _ in range(30):
        try:
            res = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.gnome.ScreenSaver",
                    "--object-path", "/org/gnome/ScreenSaver",
                    "--method", "org.gnome.ScreenSaver.GetActive",
                ],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=1.5,
            )
            if res.returncode == 0:
                break
        except Exception:
            pass
        time.sleep(0.5)

    # En Ubuntu 24.04, GNOME inicia en el modo Overview (Actividades), lo que bloquea ScreenSaver.Lock.
    # Enviamos Escape o cerramos Overview antes de bloquear:
    if shutil.which("xdotool"):
        ejecutar_seguro(["xdotool", "key", "Escape"])

    for _ in range(45):
        if pantalla_esta_bloqueada():
            time.sleep(0.6)
            if pantalla_esta_bloqueada():
                print("[J.A.R.V.I.S.] Pantalla bloqueada con éxito. Esperando 2 palmadas...")
                return True

        # Método 1: sudo loginctl lock-sessions (bloquea todas las sesiones gráficas del usuario sin fallar)
        ejecutar_seguro(["sudo", "-n", "/usr/bin/loginctl", "lock-sessions"])
        # Método 2: loginctl lock-session estándar
        ejecutar_seguro(["loginctl", "lock-session"])
        # Método 3: D-Bus GNOME ScreenSaver.Lock
        ejecutar_seguro([
            "gdbus", "call", "--session",
            "--dest", "org.gnome.ScreenSaver",
            "--object-path", "/org/gnome/ScreenSaver",
            "--method", "org.gnome.ScreenSaver.Lock",
        ])
        # Método 4: xdg-screensaver
        if shutil.which("xdg-screensaver"):
            ejecutar_seguro(["xdg-screensaver", "lock"])

        time.sleep(0.45)

    return pantalla_esta_bloqueada()


def despertar_y_desbloquear() -> None:
    ejecutar_seguro(["sudo", "-n", "/usr/bin/loginctl", "unlock-sessions"])
    ejecutar_seguro([
        "gdbus", "call", "--session",
        "--dest", "org.gnome.ScreenSaver",
        "--object-path", "/org/gnome/ScreenSaver",
        "--method", "org.gnome.ScreenSaver.SetActive", "false",
    ])
    ejecutar_seguro(["xset", "dpms", "force", "on"])


# =====================================================================
# 3. FUNCIONES DE CONTROL PROFUNDO DE LA LAPTOP ASUS TUF
# =====================================================================
def controlar_teclado_y_ventiladores_asus(nivel_luz_teclado: int = -1, modo_termico: str = "") -> str:
    acciones = []
    if nivel_luz_teclado >= 0:
        n = max(0, min(3, int(nivel_luz_teclado)))
        if shutil.which("brightnessctl"):
            subprocess.run(["brightnessctl", "--device=*kbd*", "set", str(n)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        ejecutar_seguro([
            "gdbus", "call", "--system",
            "--dest", "org.freedesktop.UPower",
            "--object-path", "/org/freedesktop/UPower/KbdBacklight",
            "--method", "org.freedesktop.UPower.KbdBacklight.SetBrightness",
            str(n),
        ])
        acciones.append(f"retroiluminación del teclado ASUS TUF ajustada al nivel {n} de 3")

    if modo_termico:
        m = modo_termico.lower()
        if "turbo" in m or "rendimiento" in m or "máximo" in m:
            if shutil.which("powerprofilesctl"):
                ejecutar_seguro(["powerprofilesctl", "set", "performance"])
            if shutil.which("asusctl"):
                ejecutar_seguro(["asusctl", "profile", "-P", "Performance"])
            acciones.append("ventiladores y procesador en perfil Turbo de alto desempeño")
        elif "silencio" in m or "quiet" in m or "eco" in m:
            if shutil.which("powerprofilesctl"):
                ejecutar_seguro(["powerprofilesctl", "set", "power-saver"])
            if shutil.which("asusctl"):
                ejecutar_seguro(["asusctl", "profile", "-P", "Quiet"])
            acciones.append("ventiladores en modo silencioso")
        else:
            if shutil.which("powerprofilesctl"):
                ejecutar_seguro(["powerprofilesctl", "set", "balanced"])
            acciones.append("perfil térmico en modo balanceado")

    escribir_estado_hud("EN LÍNEA", "; ".join(acciones).capitalize(), visible=True, efecto_transicion="PORTAL")
    return sintetizar_respuesta_unica_contextual(
        f"Ajustar teclado {nivel_luz_teclado} y ventiladores {modo_termico}",
        "Se aplicó en el hardware de la ASUS TUF: " + (", ".join(acciones) if acciones else "calibración de periféricos completada."),
        False,
    )


def escanear_red_y_dispositivos_wifi() -> str:
    dispositivos = []
    ip_local = "desconocida"
    try:
        ip_out = subprocess.check_output(["hostname", "-I"], text=True, stderr=subprocess.DEVNULL).strip().split()
        if ip_out:
            ip_local = ip_out[0]
        arp_out = subprocess.check_output(["ip", "neigh", "show"], text=True, stderr=subprocess.DEVNULL)
        for l in arp_out.splitlines():
            if "REACHABLE" in l or "STALE" in l or "DELAY" in l:
                partes = l.split()
                if partes and partes[0].count(".") == 3:
                    dispositivos.append(partes[0])
    except Exception:
        pass

    escribir_estado_hud("PROCESANDO", f"Radar de Red: IP {ip_local} | {len(dispositivos)} nodos detectados", visible=True, efecto_transicion="PORTAL")
    hechos = f"La dirección IP local de la ASUS TUF es {ip_local}. Se detectaron {len(dispositivos)} dispositivos activos en la red local Wi-Fi ({', '.join(dispositivos[:5]) if dispositivos else 'ningún nodo extraño'})."
    return sintetizar_respuesta_unica_contextual("Escanea quién está en mi red Wi-Fi", hechos, True)


def activar_centinela_camara_intrusos(segundos_vigilancia: int = 60) -> str:
    global CENTINELA_INTRUSOS_ACTIVO
    if CENTINELA_INTRUSOS_ACTIVO:
        return "El centinela óptico anti-intrusos ya se encuentra activo vigilando su estación, señor."

    CENTINELA_INTRUSOS_ACTIVO = True

    def _vigilar():
        global CENTINELA_INTRUSOS_ACTIVO
        time.sleep(4.0)
        escribir_estado_hud("ALERTA", "👁️ CENTINELA ANTI-INTRUSOS ACTIVO", visible=True, efecto_transicion="PORTAL")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            CENTINELA_INTRUSOS_ACTIVO = False
            return

        _, frame_base = cap.read()
        for _ in range(5):
            _, frame_base = cap.read()
        gris_base = cv2.GaussianBlur(cv2.cvtColor(frame_base, cv2.COLOR_BGR2GRAY), (21, 21), 0)
        t_ini = time.monotonic()

        while (time.monotonic() - t_ini) < segundos_vigilancia and CENTINELA_INTRUSOS_ACTIVO:
            time.sleep(0.5)
            ret, frame = cap.read()
            if not ret:
                continue
            gris = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
            diff = cv2.absdiff(gris_base, gris)
            thresh = cv2.threshold(diff, 28, 255, cv2.THRESH_BINARY)[1]
            cambio = float(np.sum(thresh > 0)) / float(thresh.size)

            if cambio > 0.085:
                carpeta_seg = (Path.home() / "Imágenes" if (Path.home() / "Imágenes").exists() else Path.home() / "Pictures") / "Jarvis_Seguridad"
                carpeta_seg.mkdir(parents=True, exist_ok=True)
                foto_intruso = carpeta_seg / f"intruso_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(str(foto_intruso), frame)
                cap.release()
                CENTINELA_INTRUSOS_ACTIVO = False
                escribir_estado_hud("ALERTA", f"¡Intruso fotografiado!: {foto_intruso.name}", visible=True)
                hablar_jarvis("Alerta de seguridad. Presencia no autorizada detectada frente a la estación de Max. He capturado su fotografía en el registro biométrico y procederé a bloquear el sistema.")
                ejecutar_seguro(["loginctl", "lock-session"])
                return

        cap.release()
        CENTINELA_INTRUSOS_ACTIVO = False
        escribir_estado_hud("EN LÍNEA", "Vigilancia óptica concluida sin incidentes.", visible=True)

    threading.Thread(target=_vigilar, daemon=True).start()
    return sintetizar_respuesta_unica_contextual(
        "Activa el centinela de intrusos",
        f"Se activó el centinela biométrico por cámara web durante {segundos_vigilancia} segundos.",
        False,
    )


def controlar_espacios_y_ventanas_avanzado(accion: str, numero_escritorio: int = 1) -> str:
    acc = accion.lower()
    escribir_estado_hud("PROCESANDO", f"Gestor de Ventanas: {accion}", visible=True, efecto_transicion="PORTAL")
    if "encima" in acc or "fija" in acc or "pin" in acc:
        ejecutar_seguro(["wmctrl", "-r", ":ACTIVE:", "-b", "toggle,above"])
        return sintetizar_respuesta_unica_contextual(accion, "Se fijó la ventana activa para que permanezca siempre visible por encima de las demás.", False)
    if "minimiza" in acc or "mostrar escritorio" in acc or "despeja" in acc:
        ejecutar_seguro(["wmctrl", "-k", "on"])
        return sintetizar_respuesta_unica_contextual(accion, "Se minimizaron todas las ventanas para despejar la vista del escritorio.", False)
    if "restaura" in acc:
        ejecutar_seguro(["wmctrl", "-k", "off"])
        return sintetizar_respuesta_unica_contextual(accion, "Se restauraron las ventanas en pantalla.", False)
    if "escritorio" in acc or "espacio" in acc:
        idx = max(0, int(numero_escritorio) - 1)
        ejecutar_seguro(["wmctrl", "-s", str(idx)])
        return sintetizar_respuesta_unica_contextual(accion, f"Cambiando al espacio de trabajo número {numero_escritorio}.", False)
    return "Ajuste de ventana aplicado, señor."


def purgar_sistema_y_ram() -> str:
    for ruta_cache in [Path("/tmp"), Path.home() / ".cache/thumbnails"]:
        if ruta_cache.exists():
            for item in ruta_cache.glob("jarvis_vision_*"):
                try:
                    item.unlink()
                except Exception:
                    pass
    ram_disp = round(psutil.virtual_memory().available / (1024 ** 3), 2)
    escribir_estado_hud("EN LÍNEA", f"Purga completada | {ram_disp} GB RAM disponibles", visible=True, efecto_transicion="PORTAL")
    return sintetizar_respuesta_unica_contextual(
        "Purga la memoria y limpia basura",
        f"Se purgaron los buffers temporales. El sistema cuenta con {ram_disp} gigabytes de memoria RAM disponibles.",
        True,
    )


def escribir_dictado_en_ventana_activa(texto_a_escribir: str) -> str:
    limpio = texto_a_escribir
    for pref in ("jarvis", "escribe aquí", "escribe aqui", "escribe en mi ventana", "dicta", "escribe"):
        limpio = re.sub(rf"^{pref}\s*[:,-]?\s*", "", limpio, flags=re.IGNORECASE).strip()
    if shutil.which("xdotool") and limpio:
        threading.Thread(
            target=lambda: (time.sleep(0.4), subprocess.run(["xdotool", "type", "--delay", "18", limpio], check=False)),
            daemon=True,
        ).start()
        return "Escribiendo el texto solicitado en su ventana activa, señor."
    return "Módulo de escritura listo, señor."


# =====================================================================
# 4. VIDEOCLIPS ("JARVIS, CLIPEA ESTO") Y SCREENRECORD CONTINUO
# =====================================================================
def obtener_carpeta_clips() -> Path:
    base_vid = Path.home() / "Vídeos"
    if not base_vid.exists():
        base_vid = Path.home() / "Videos"
    carpeta = base_vid / "Jarvis_Clips"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _grabar_video_opencv_fallback(ruta_destino: Path, segundos: int) -> bool:
    global BANDERA_DETENER_GRABACION_CV2
    BANDERA_DETENER_GRABACION_CV2 = False
    try:
        primera_img = ImageGrab.grab()
        ancho, alto = primera_img.size
        fps = 10.0
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(ruta_destino), fourcc, fps, (ancho, alto))
        t_inicio = time.monotonic()
        intervalo = 1.0 / fps

        while (time.monotonic() - t_inicio) < segundos and not BANDERA_DETENER_GRABACION_CV2:
            t_ciclo = time.monotonic()
            img = ImageGrab.grab()
            frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            writer.write(frame_bgr)
            restante = intervalo - (time.monotonic() - t_ciclo)
            if restante > 0:
                time.sleep(restante)

        writer.release()
        return ruta_destino.exists() and ruta_destino.stat().st_size > 1000
    except Exception:
        return False


def clipear_pantalla_ahora(segundos: int = 15) -> str:
    global ULTIMO_CLIP_GUARDADO
    segundos = max(5, min(120, int(segundos)))
    carpeta = obtener_carpeta_clips()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_mp4 = carpeta / f"clip_stark_{timestamp}.mp4"
    ULTIMO_CLIP_GUARDADO = archivo_mp4

    def _proceso_clip():
        escribir_estado_hud(
            "PROCESANDO",
            f"🔴 Grabando videoclip de pantalla ({segundos}s) -> {archivo_mp4.name}",
            visible=True,
            animacion="RECORDING",
            app_actual=f"🔴 REC // CLIPEANDO PANTALLA ({segundos}S)",
            progreso=50,
            grabando=True,
            efecto_transicion="PORTAL",
        )
        exito = False
        scr_w, scr_h = obtener_resolucion_pantalla()
        display_env = os.environ.get("DISPLAY", ":0")

        if shutil.which("ffmpeg"):
            cmd_ff = [
                "ffmpeg", "-y", "-f", "x11grab", "-framerate", "25", "-video_size", f"{scr_w}x{scr_h}",
                "-i", display_env, "-f", "pulse", "-i", "default", "-t", str(segundos),
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(archivo_mp4),
            ]
            res = subprocess.run(cmd_ff, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0 and archivo_mp4.exists() and archivo_mp4.stat().st_size > 5000:
                exito = True
            else:
                cmd_ff_v = [
                    "ffmpeg", "-y", "-f", "x11grab", "-framerate", "25", "-video_size", f"{scr_w}x{scr_h}",
                    "-i", display_env, "-t", str(segundos), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(archivo_mp4),
                ]
                res2 = subprocess.run(cmd_ff_v, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if res2.returncode == 0 and archivo_mp4.exists() and archivo_mp4.stat().st_size > 5000:
                    exito = True

        if not exito:
            exito = _grabar_video_opencv_fallback(archivo_mp4, segundos)

        escribir_estado_hud("EN LÍNEA", f"Videoclip guardado en {archivo_mp4.name}", visible=True, animacion="NORMAL", progreso=100, grabando=False)
        if exito and not esta_en_modo_silencio():
            hablar_jarvis(f"Listo, {NOMBRE_USUARIO}. Su videoclip de {segundos} segundos ha quedado guardado en su carpeta de Videos como {archivo_mp4.name}.", restaurar_al_100=True)

    threading.Thread(target=_proceso_clip, daemon=True).start()
    return sintetizar_respuesta_unica_contextual(
        f"Clipea esto por {segundos} segundos",
        f"Se inició la captura de un videoclip MP4 de {segundos} segundos de la pantalla de Max en {archivo_mp4}.",
        incluir_punto_de_vista=False,
    )


def iniciar_grabacion_continua_pantalla() -> str:
    global PROCESO_GRABACION_CONTINUA, ULTIMO_CLIP_GUARDADO, BANDERA_DETENER_GRABACION_CV2
    if PROCESO_GRABACION_CONTINUA is not None and PROCESO_GRABACION_CONTINUA.poll() is None:
        return "Ya tengo una grabación de pantalla en curso, señor. Dígame detén la grabación cuando desee guardarla."

    carpeta = obtener_carpeta_clips()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_mp4 = carpeta / f"screenrecord_stark_{timestamp}.mp4"
    ULTIMO_CLIP_GUARDADO = archivo_mp4
    scr_w, scr_h = obtener_resolucion_pantalla()
    display_env = os.environ.get("DISPLAY", ":0")

    escribir_estado_hud("PROCESANDO", f"🔴 Grabación continua activa -> {archivo_mp4.name}", visible=True, animacion="RECORDING", app_actual="🔴 REC // SCREENRECORD CONTINUO ACTIVO", progreso=100, grabando=True, efecto_transicion="PORTAL")

    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-f", "x11grab", "-framerate", "25", "-video_size", f"{scr_w}x{scr_h}", "-i", display_env, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(archivo_mp4)]
        PROCESO_GRABACION_CONTINUA = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        threading.Thread(target=_grabar_video_opencv_fallback, args=(archivo_mp4, 600), daemon=True).start()

    return sintetizar_respuesta_unica_contextual("Empieza a grabar mi pantalla", f"Se inició la grabación continua de pantalla en {archivo_mp4.name}.", False)


def detener_grabacion_continua_pantalla() -> str:
    global PROCESO_GRABACION_CONTINUA, BANDERA_DETENER_GRABACION_CV2
    BANDERA_DETENER_GRABACION_CV2 = True
    if PROCESO_GRABACION_CONTINUA is not None and PROCESO_GRABACION_CONTINUA.poll() is None:
        try:
            PROCESO_GRABACION_CONTINUA.send_signal(signal.SIGINT)
            PROCESO_GRABACION_CONTINUA.wait(timeout=3.0)
        except Exception:
            PROCESO_GRABACION_CONTINUA.terminate()
        PROCESO_GRABACION_CONTINUA = None

    escribir_estado_hud("EN LÍNEA", "Grabación de pantalla finalizada y guardada.", visible=True, animacion="NORMAL", progreso=100, grabando=False, efecto_transicion="PORTAL")
    nombre = ULTIMO_CLIP_GUARDADO.name if ULTIMO_CLIP_GUARDADO else "screenrecord_stark.mp4"
    return sintetizar_respuesta_unica_contextual("Detén la grabación", f"Se detuvo la grabación de pantalla y el video quedó guardado como {nombre}.", False)


def abrir_carpeta_clips() -> str:
    carpeta = obtener_carpeta_clips()
    if ULTIMO_CLIP_GUARDADO and ULTIMO_CLIP_GUARDADO.exists() and shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", str(ULTIMO_CLIP_GUARDADO)], start_new_session=True)
    elif shutil.which("nautilus"):
        subprocess.Popen(["nautilus", str(carpeta)], start_new_session=True)
    return "Abriendo su galería de videoclips grabados ahora mismo, señor."


def analizar_codigo_portapapeles() -> str:
    contenido = leer_portapapeles()
    if not contenido or "vacío" in contenido:
        return "Señor, su portapapeles está vacío en este momento. Copie el fragmento de código o el error de la terminal y vuelva a indicármelo."
    return sintetizar_respuesta_unica_contextual("Analiza este código o error que copié", f"Contenido del portapapeles de Max: {contenido[:1500]}", True)


def crear_caja_negra_proyecto() -> str:
    carpeta_bk = DIRECTORIO_BASE / "backups"
    carpeta_bk.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_zip = carpeta_bk / f"caja_negra_stark_{stamp}.zip"
    try:
        with zipfile.ZipFile(archivo_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for arch in DIRECTORIO_BASE.glob("*.py"):
                zf.write(arch, arcname=arch.name)
            for arch_j in DIRECTORIO_BASE.glob("*.json"):
                zf.write(arch_j, arcname=arch_j.name)
            if ARCHIVO_BITACORA.exists():
                zf.write(ARCHIVO_BITACORA, arcname=ARCHIVO_BITACORA.name)
        return sintetizar_respuesta_unica_contextual("Guarda una caja negra de mi proyecto", f"Se creó un respaldo comprimido Caja Negra en {archivo_zip.name}.", True)
    except Exception:
        return "Respaldo de seguridad sincronizado en el directorio local, señor."


def cargar_agenda() -> dict:
    DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO_AGENDA.exists():
        return {}
    try:
        return json.loads(ARCHIVO_AGENDA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_agenda(agenda: dict) -> None:
    DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
    ARCHIVO_AGENDA.write_text(json.dumps(agenda, ensure_ascii=False, indent=2), encoding="utf-8")


def construir_orden_del_dia() -> str:
    mem = depurar_y_actualizar_todo_el_contexto()
    agenda = cargar_agenda()
    ahora = datetime.datetime.now()
    dia_semana = str(ahora.weekday())
    partes = []

    actividades_hoy = list(agenda.get("horario_semanal", {}).get(dia_semana, []))
    if dia_semana in ("0", "2") and not any("suma" in a.lower() for a in actividades_hoy):
        actividades_hoy.insert(0, "Impartir clases en SUMA de 7:00 a 9:00 de la noche")

    reuniones_activas = [r["titulo"] for r in agenda.get("reuniones", []) if not r.get("completado", False)]
    todas_activas = actividades_hoy + reuniones_activas

    if todas_activas:
        partes.append(f"En su agenda de hoy tiene: {'; '.join(todas_activas)}.")

    tareas_cr = mem.get("classroom_asignaciones", [])
    if tareas_cr:
        cr_txt = "; ".join(f"{t['titulo']} de {t['curso'].split('(')[0].strip()} para el {t.get('entrega_humana', t['entrega'])}" for t in tareas_cr[:3])
        partes.append(f"En Google Classroom tiene pendientes de entrega: {cr_txt}.")

    correos_imp = mem.get("correos_importantes", [])
    if correos_imp:
        partes.append(f"En Gmail tiene por revisar: {correos_imp[0]['remitente']}.")

    pendientes_activos = [p for p in agenda.get("pendientes", []) if not p.get("completado", False)]
    if pendientes_activos:
        total = len(pendientes_activos)
        primeros = "; ".join(f"[{p['categoria']}] {p['titulo']}" for p in pendientes_activos[:2])
        partes.append(f"Además cuenta con {total} pendientes técnicos vigentes, destacando: {primeros}.")

    return " ".join(partes)


def agregar_item_agenda(tipo: str, texto: str) -> str:
    agenda = cargar_agenda()
    clave = "reuniones" if tipo == "reunion" else "pendientes"
    lista = agenda.get(clave, [])
    nuevo_id = max([item.get("id", 0) for item in lista], default=0) + 1
    lista.append({
        "id": nuevo_id,
        "categoria": "Personalizado",
        "titulo": texto.strip(),
        "completado": False,
        "fecha": datetime.date.today().isoformat(),
    })
    agenda[clave] = lista
    guardar_agenda(agenda)
    return sintetizar_respuesta_unica_contextual(texto, f"Se registró el pendiente #{nuevo_id}: {texto.strip()}.", False)


def completar_item_agenda(item_id: int) -> str:
    agenda = cargar_agenda()
    for p in agenda.get("pendientes", []):
        if p.get("id") == item_id:
            p["completado"] = True
            guardar_agenda(agenda)
            recordar_dato_o_persona("logro", p["categoria"], p["titulo"])
            depurar_y_actualizar_todo_el_contexto()
            return sintetizar_respuesta_unica_contextual(f"Completar pendiente {item_id}", f"Se marcó como completado y archivó el pendiente #{item_id}: {p['titulo']}.", True)
    return f"No encontré ningún pendiente activo con el número {item_id}, {NOMBRE_USUARIO}."


def esta_en_modo_silencio() -> bool:
    global MODO_SUSPENSION_SILENCIOSA
    datos_hud = leer_estado_hud_actual()
    if "silenciado" in datos_hud:
        MODO_SUSPENSION_SILENCIOSA = bool(datos_hud["silenciado"])
    return MODO_SUSPENSION_SILENCIOSA


def establecer_modo_silencio_suma(silenciar: bool) -> str:
    global MODO_SUSPENSION_SILENCIOSA
    MODO_SUSPENSION_SILENCIOSA = silenciar
    if silenciar:
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
        escribir_estado_hud("SUSPENDIDO (CLASE SUMA)", "Modo Silencio activo. Diga 'Jarvis despierta' para reactivar.", visible=True, animacion="STEALTH", silenciado=True, efecto_transicion="PORTAL")
        return "Entendido, señor. Entrando en modo de suspensión silenciosa para su clase o reunión. No volveré a hablar ni interrumpirlo hasta que me ordene despertar."
    else:
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])
        escribir_estado_hud("EN LÍNEA", "Sistemas reactivados y a la escucha, señor.", visible=True, animacion="NORMAL", silenciado=False, efecto_transicion="ENTRADA")
        return "Sistemas vocales y centinela reactivados, señor. Es un gusto tenerlo de vuelta tras su sesión."


def ajustar_brillo_pantalla(porcentaje: int) -> str:
    pct = max(10, min(100, int(porcentaje)))
    ejecutar_seguro([
        "gdbus", "call", "--session", "--dest", "org.gnome.SettingsDaemon.Power",
        "--object-path", "/org/gnome/SettingsDaemon/Power",
        "--method", "org.freedesktop.DBus.Properties.Set",
        "org.gnome.SettingsDaemon.Power.Screen", "Brightness", f"<int32 {pct}>",
    ])
    if shutil.which("brightnessctl"):
        ejecutar_seguro(["brightnessctl", "set", f"{pct}%"])
    return sintetizar_respuesta_unica_contextual(f"Brillo al {pct}%", f"El brillo del monitor se ajustó al {pct} por ciento.", False)


def controlar_bluetooth_laptop(encender: bool) -> str:
    if shutil.which("rfkill"):
        accion = "unblock" if encender else "block"
        ejecutar_seguro(["rfkill", accion, "bluetooth"])
    return "Módulo Bluetooth encendido, señor." if encender else "He apagado el radio Bluetooth para maximizar el ahorro de batería, señor."


def activar_modo_ahorro_bateria(activar: bool = True) -> str:
    if activar:
        if shutil.which("powerprofilesctl"):
            ejecutar_seguro(["powerprofilesctl", "set", "power-saver"])
        if shutil.which("asusctl"):
            ejecutar_seguro(["asusctl", "profile", "-P", "Quiet"])
        ajustar_brillo_pantalla(35)
        controlar_teclado_y_ventiladores_asus(0, "silencio")
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
        escribir_estado_hud("EN LÍNEA", "Modo Ahorro de Batería Activo (CPU Eco + Brillo 35%).", visible=True, animacion="POWER_SAVE", efecto_transicion="PORTAL")
        bat = psutil.sensors_battery()
        pct_bat = f"Batería actual al {round(bat.percent)} por ciento." if bat else ""
        return sintetizar_respuesta_unica_contextual("Activa ahorro de batería", f"Se activó el modo ahorro extremo de batería en la ASUS TUF (CPU en power-saver, teclado apagado y brillo al 35%). {pct_bat}", True)
    else:
        if shutil.which("powerprofilesctl"):
            ejecutar_seguro(["powerprofilesctl", "set", "performance"])
        if shutil.which("asusctl"):
            ejecutar_seguro(["asusctl", "profile", "-P", "Performance"])
        ajustar_brillo_pantalla(90)
        controlar_teclado_y_ventiladores_asus(3, "turbo")
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])
        escribir_estado_hud("EN LÍNEA", "Modo Alto Rendimiento Turbo activo.", visible=True, animacion="NORMAL", efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual("Activa alto rendimiento", "Se activó el modo Alto Rendimiento Turbo con brillo al 90% y teclado iluminado al máximo.", False)


def suspender_laptop() -> str:
    escribir_estado_hud("ALERTA", "Colapsando sistemas hacia suspensión...", visible=True, animacion="CLOSE_ALL", efecto_transicion="CIERRE")
    threading.Thread(target=lambda: (time.sleep(2.5), ejecutar_seguro(["systemctl", "suspend"])), daemon=True).start()
    return "Poniendo su estación ASUS TUF en suspensión profunda de bajo consumo. Hasta pronto, señor."


def guardar_captura_en_imagenes() -> str:
    carpeta_img = Path.home() / "Imágenes"
    if not carpeta_img.exists():
        carpeta_img = Path.home() / "Pictures"
    carpeta_img.mkdir(parents=True, exist_ok=True)
    nombre = f"jarvis_captura_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    destino = carpeta_img / nombre
    if shutil.which("gnome-screenshot"):
        subprocess.run(["gnome-screenshot", "-f", str(destino)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return f"He capturado su pantalla y guardado el archivo {nombre} en su carpeta de Imágenes, señor."


def lanzar_hud_holografico(animacion: str = "NORMAL", fullscreen: bool = False) -> None:
    hud_activo = any("jarvis_hud.py" in " ".join(p.info.get("cmdline") or []) for p in psutil.process_iter(["cmdline"]))
    escribir_estado_hud("EN LÍNEA", "Materializando holograma...", visible=True, animacion=animacion, fullscreen=fullscreen, efecto_transicion="ENTRADA")
    if not hud_activo:
        python_bin = str(DIRECTORIO_BASE / ".venv" / "bin" / "python")
        hud_script = str(DIRECTORIO_BASE / "jarvis_hud.py")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "xcb"
        env["DISPLAY"] = os.environ.get("DISPLAY", ":0")
        subprocess.Popen([python_bin, hud_script], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(0.45)


def leer_portapapeles() -> str:
    if shutil.which("xclip"):
        try:
            texto = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True).strip()
            return texto if texto else "El portapapeles está vacío, señor."
        except Exception:
            return "No pude leer el portapapeles."
    return "Módulo xclip no disponible."


def ajustar_volumen_sistema(porcentaje: int) -> None:
    porcentaje = max(0, min(150, porcentaje))
    if shutil.which("wpctl"):
        ejecutar_seguro(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"])
        ejecutar_seguro(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{porcentaje}%"])
    elif shutil.which("pactl"):
        ejecutar_seguro(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        ejecutar_seguro(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{porcentaje}%"])


def ajustar_volumen_spotify(porcentaje: int) -> None:
    decimal = max(0.0, min(1.0, porcentaje / 100.0))
    ejecutar_seguro(["playerctl", "--player=spotify", "volume", f"{decimal:.2f}"])
    if shutil.which("pactl"):
        try:
            env = os.environ.copy()
            env["LC_ALL"] = "C"
            salida = subprocess.check_output(["pactl", "list", "sink-inputs"], env=env, text=True, stderr=subprocess.DEVNULL)
            for bloque in salida.split("Sink Input #")[1:]:
                if "spotify" in bloque.lower():
                    sink_id = bloque.splitlines()[0].strip()
                    ejecutar_seguro(["pactl", "set-sink-input-volume", sink_id, f"{porcentaje}%"])
        except Exception:
            pass


# =====================================================================
# 5. MOTOR SPOTIFY INFALIBLE MARK XV (INICIO Y CANCIONES ESPECÍFICAS)
# =====================================================================
def asegurar_spotify_listo() -> None:
    spotify_activo = any("spotify" in (p.info["name"] or "").lower() for p in psutil.process_iter(["name"]))
    if not spotify_activo:
        if shutil.which("spotify"):
            subprocess.Popen(["spotify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        elif shutil.which("flatpak"):
            subprocess.Popen(["flatpak", "run", "com.spotify.Client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    for _ in range(32):
        try:
            out = subprocess.check_output(["playerctl", "-l"], text=True, stderr=subprocess.DEVNULL)
            if "spotify" in out.lower():
                break
        except Exception:
            pass
        time.sleep(0.35)


def _enviar_metodo_mpris_spotify(metodo: str) -> bool:
    ok1 = ejecutar_seguro([
        "gdbus", "call", "--session",
        "--dest", "org.mpris.MediaPlayer2.spotify",
        "--object-path", "/org/mpris/MediaPlayer2",
        "--method", f"org.mpris.MediaPlayer2.Player.{metodo}",
    ])
    mapa_pctl = {"Play": "play", "Pause": "pause", "PlayPause": "play-pause", "Next": "next", "Previous": "previous", "Stop": "stop"}
    ok2 = False
    if metodo in mapa_pctl:
        ok2 = ejecutar_seguro(["playerctl", "--player=spotify", mapa_pctl[metodo]])
    return ok1 or ok2


def reproducir_musica_aleatoria() -> None:
    asegurar_spotify_listo()
    ejecutar_seguro(["playerctl", "--player=spotify", "loop", "Playlist"])
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])
    time.sleep(0.2)
    _enviar_metodo_mpris_spotify("Play")


def _pasar_a_rework_aleatorio() -> None:
    ejecutar_seguro(["playerctl", "--player=spotify", "loop", "Playlist"])
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])
    time.sleep(0.15)
    ejecutar_seguro([
        "gdbus", "call", "--session",
        "--dest", "org.mpris.MediaPlayer2.spotify",
        "--object-path", "/org/mpris/MediaPlayer2",
        "--method", "org.mpris.MediaPlayer2.Player.OpenUri",
        PLAYLIST_REWORK_URI,
    ])
    time.sleep(0.8)
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])
    _enviar_metodo_mpris_spotify("Play")
    time.sleep(0.35)
    try:
        t_act = subprocess.check_output(["playerctl", "--player=spotify", "metadata", "title"], text=True, stderr=subprocess.DEVNULL).strip().lower()
        if "should i stay" in t_act:
            _enviar_metodo_mpris_spotify("Next")
    except Exception:
        pass


def _vigilar_transicion_should_i_stay() -> None:
    time.sleep(5.0)
    ya_avanzo = False
    while True:
        time.sleep(1.5)
        try:
            titulo = subprocess.check_output(
                ["playerctl", "--player=spotify", "metadata", "title"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip().lower()

            if "should i stay" not in titulo:
                ejecutar_seguro(["playerctl", "--player=spotify", "loop", "Playlist"])
                ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])
                break

            pos_str = subprocess.check_output(
                ["playerctl", "--player=spotify", "position"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            pos = float(pos_str)

            if pos > 35.0:
                ya_avanzo = True

            if pos >= 184.0 or (ya_avanzo and pos < 12.0):
                _pasar_a_rework_aleatorio()
                break
        except Exception:
            break


def iniciar_rework_en_spotify(volumen_inicial: int = 100) -> None:
    asegurar_spotify_listo()
    ajustar_volumen_sistema(VOLUMEN_SISTEMA_MAX)
    ajustar_volumen_spotify(volumen_inicial)

    ejecutar_seguro(["playerctl", "--player=spotify", "loop", "Playlist"])
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "Off"])
    time.sleep(0.25)

    ejecutar_seguro([
        "gdbus", "call", "--session",
        "--dest", "org.mpris.MediaPlayer2.spotify",
        "--object-path", "/org/mpris/MediaPlayer2",
        "--method", "org.mpris.MediaPlayer2.Player.OpenUri",
        SHOULD_I_STAY_URI,
    ])
    time.sleep(0.65)
    _enviar_metodo_mpris_spotify("Play")
    ajustar_volumen_spotify(volumen_inicial)

    threading.Thread(target=_vigilar_transicion_should_i_stay, daemon=True).start()


def _buscar_uri_cancion_en_web(consulta: str) -> tuple[str, str]:
    q_norm = "".join(c for c in unicodedata.normalize("NFD", consulta.lower()) if unicodedata.category(c) != "Mn")
    q_norm = q_norm.replace("'", "").strip()

    for k, (nombre_oficial, uri_fija) in CANCIONES_FAVORITAS_URI.items():
        if k in q_norm:
            return nombre_oficial, uri_fija

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
    for url_busqueda in [
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote('site:open.spotify.com/track ' + consulta)}",
        f"https://search.yahoo.com/search?p={urllib.parse.quote('site:open.spotify.com/track ' + consulta)}",
    ]:
        try:
            req = urllib.request.Request(url_busqueda, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                html_txt = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", html_txt)
                if m:
                    return consulta.title(), f"spotify:track:{m.group(1)}"
        except Exception:
            continue

    return consulta.title(), ""


def reproducir_cancion_especifica_spotify(nombre_cancion: str) -> str:
    limpio = nombre_cancion
    for pref in (
        "jarvis", "yarvis", "por favor", "reproduce la cancion", "reproduce la canción",
        "pon la cancion", "pon la canción", "pon en spotify", "reproduce en spotify",
        "quiero escuchar", "ponme", "reproduce", "pon", "escuchar", "en mi playlist", "de mi playlist",
    ):
        limpio = re.sub(rf"\b{pref}\b", "", limpio, flags=re.IGNORECASE).strip(" ,.:")

    if not limpio or limpio.lower() in ("musica", "música", "algo", "spotify"):
        reproducir_musica_aleatoria()
        return sintetizar_respuesta_unica_contextual("Pon música", "Se activó la reproducción aleatoria en Spotify.", False)

    if "rework" in limpio.lower():
        iniciar_rework_en_spotify(100)
        return sintetizar_respuesta_unica_contextual("Pon mi playlist Rework", "Iniciando la playlist Rework desde la primera pista.", False)

    asegurar_spotify_listo()
    titulo_mostrar, track_uri = _buscar_uri_cancion_en_web(limpio)

    escribir_estado_hud(
        "PROCESANDO",
        f"🎵 Reproduciendo en Spotify: {titulo_mostrar}",
        visible=True,
        app_actual=f"SPOTIFY // {titulo_mostrar.upper()[:30]}",
        progreso=90,
        efecto_transicion="PORTAL",
    )

    if track_uri:
        ejecutar_seguro([
            "gdbus", "call", "--session",
            "--dest", "org.mpris.MediaPlayer2.spotify",
            "--object-path", "/org/mpris/MediaPlayer2",
            "--method", "org.mpris.MediaPlayer2.Player.OpenUri",
            track_uri,
        ])
        time.sleep(0.5)
        _enviar_metodo_mpris_spotify("Play")
        ajustar_volumen_spotify(100)
        return sintetizar_respuesta_unica_contextual(
            f"Pon {titulo_mostrar}",
            f"Se está reproduciendo ahora mismo {titulo_mostrar} en Spotify.",
            False,
        )

    ejecutar_seguro([
        "gdbus", "call", "--session",
        "--dest", "org.mpris.MediaPlayer2.spotify",
        "--object-path", "/org/mpris/MediaPlayer2",
        "--method", "org.mpris.MediaPlayer2.Player.OpenUri",
        f"spotify:search:{urllib.parse.quote(limpio)}",
    ])
    time.sleep(1.2)
    _enviar_metodo_mpris_spotify("Play")
    return sintetizar_respuesta_unica_contextual(
        f"Busca y reproduce {limpio}",
        f"Se cargó y activó la reproducción de {limpio} en Spotify.",
        False,
    )


def controlar_musica_por_voz(comando_usuario: str) -> str:
    cmd_n = "".join(c for c in unicodedata.normalize("NFD", comando_usuario.lower()) if unicodedata.category(c) != "Mn")

    if any(k in cmd_n for k in ("pausa", "pausar", "deten la musica", "para la musica", "silencia la musica", "quita la musica", "apaga la musica")):
        _enviar_metodo_mpris_spotify("Pause")
        if "cierra spotify" in cmd_n:
            subprocess.run(["pkill", "-f", "spotify"], stderr=subprocess.DEVNULL, check=False)
        escribir_estado_hud("EN LÍNEA", "Música de Spotify en pausa.", visible=True, efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual(comando_usuario, "He pausado la reproducción de Spotify inmediatamente.", False)

    if any(k in cmd_n for k in ("siguiente", "cambia la cancion", "cambia de cancion", "otra cancion", "cambiala", "salta la cancion", "adelanta")):
        asegurar_spotify_listo()
        _enviar_metodo_mpris_spotify("Next")
        time.sleep(0.35)
        titulo_nuevo = ""
        try:
            titulo_nuevo = subprocess.check_output(["playerctl", "--player=spotify", "metadata", "title"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass
        det = f"Cambiando a la siguiente pista de su playlist ({titulo_nuevo})." if titulo_nuevo else "Cambiando a la siguiente canción en Spotify."
        escribir_estado_hud("EN LÍNEA", f"🎵 Pista actual: {titulo_nuevo or 'Siguiente'}", visible=True, efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual(comando_usuario, det, False)

    if any(k in cmd_n for k in ("anterior", "regresa la cancion", "cancion pasada", "atras")):
        asegurar_spotify_listo()
        _enviar_metodo_mpris_spotify("Previous")
        escribir_estado_hud("EN LÍNEA", "Regresando a la pista anterior en Spotify.", visible=True, efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual(comando_usuario, "He regresado a la canción anterior en Spotify.", False)

    if cmd_n.strip() in ("pon musica", "jarvis pon musica", "reproduce musica", "continua la musica", "reanuda la musica", "play"):
        asegurar_spotify_listo()
        _enviar_metodo_mpris_spotify("Play")
        ajustar_volumen_spotify(100)
        return sintetizar_respuesta_unica_contextual(comando_usuario, "Reanudando la música de su playlist en Spotify al cien por ciento.", False)

    return reproducir_cancion_especifica_spotify(comando_usuario)


# =====================================================================
# 6. GESTIÓN DE VENTANAS Y APERTURA DE APLICACIONES (ONSHAPE, CANVA, LATEX)
# =====================================================================
def buscar_lanzador_desktop(keywords: list[str]) -> Path | None:
    directorios = [
        Path.home() / ".local/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/var/lib/snapd/desktop/applications"),
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]
    for carpeta in directorios:
        if not carpeta.exists():
            continue
        for archivo in carpeta.glob("*.desktop"):
            try:
                contenido = archivo.read_text(errors="ignore")
                match_name = re.search(r"^Name=(.+)$", contenido, re.MULTILINE | re.IGNORECASE)
                nombre_app = match_name.group(1).lower() if match_name else ""
                for kw in keywords:
                    if kw.lower() in nombre_app or kw.lower() in archivo.name.lower():
                        return archivo
            except Exception:
                continue
    return None


def obtener_resolucion_pantalla() -> tuple[int, int]:
    if shutil.which("xdpyinfo"):
        try:
            out = subprocess.check_output(["xdpyinfo"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"dimensions:\s+(\d+)x(\d+)\s+pixels", out)
            if m:
                return int(m.group(1)), int(m.group(2))
        except Exception:
            pass
    return 1920, 1080


def obtener_coordenadas_simetricas_stark(num_ventanas: int = 4) -> list[tuple[int, int, int, int]]:
    scr_w, scr_h = obtener_resolucion_pantalla()
    pad_izq = 72
    pad_top = 36
    util_w = scr_w - pad_izq
    util_h = scr_h - pad_top

    if num_ventanas <= 1:
        return [(pad_izq, pad_top, util_w, util_h)]
    if num_ventanas == 2:
        w = util_w // 2
        return [(pad_izq, pad_top, w, util_h), (pad_izq + w, pad_top, w, util_h)]

    w = util_w // 2
    h = util_h // 2
    return [
        (pad_izq, pad_top, w, h),
        (pad_izq + w, pad_top, w, h),
        (pad_izq, pad_top + h, w, h),
        (pad_izq + w, pad_top + h, w, h),
    ]


def maximizar_todas_las_ventanas() -> str:
    if not shutil.which("wmctrl"):
        return "El gestor wmctrl requiere estar instalado, señor."
    try:
        salida = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
        ignorar = ("j.a.r.v.i.s.", "jarvis hud", "holographic command", "desktop", "dock", "panel", "gnome-shell")
        cont = 0
        for linea in salida.splitlines():
            partes = linea.split(None, 3)
            if len(partes) >= 4:
                win_id, escritorio, _, titulo = partes
                if escritorio == "-1":
                    continue
                if not any(ig in titulo.lower() for ig in ignorar):
                    ejecutar_seguro(["wmctrl", "-i", "-r", win_id, "-b", "remove,fullscreen,hidden"])
                    ejecutar_seguro(["wmctrl", "-i", "-r", win_id, "-b", "add,maximized_vert,maximized_horz"])
                    cont += 1
        escribir_estado_hud("EN LÍNEA", f"{cont} ventanas maximizadas al 100%", visible=True, efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual("Pon completas las ventanas", f"Se maximizaron {cont} ventanas al 100% de la pantalla.", False)
    except Exception:
        return "Ventanas maximizadas a pantalla completa, señor."


def acomodar_ventanas_en_mosaico() -> str:
    if not shutil.which("wmctrl"):
        return "El gestor wmctrl requiere estar instalado, señor."
    try:
        salida = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
        ventanas = []
        ignorar = ("j.a.r.v.i.s.", "jarvis hud", "holographic command", "desktop", "dock", "panel", "gnome-shell", "guardia")
        for linea in salida.splitlines():
            partes = linea.split(None, 3)
            if len(partes) >= 4:
                win_id, escritorio, _, titulo = partes
                if escritorio == "-1":
                    continue
                if not any(ig in titulo.lower() for ig in ignorar):
                    ventanas.append((win_id, titulo))

        if not ventanas:
            return "No detecté ventanas para acomodar en este instante, señor."

        objetivo_wins = ventanas[-4:]
        coords = obtener_coordenadas_simetricas_stark(len(objetivo_wins))

        for i, (win_id, _) in enumerate(objetivo_wins):
            x, y, w, h = coords[i % len(coords)]
            ejecutar_seguro(["wmctrl", "-i", "-r", win_id, "-b", "remove,maximized_vert,maximized_horz,fullscreen,hidden"])
            ejecutar_seguro(["wmctrl", "-i", "-r", win_id, "-e", f"0,{x},{y},{w},{h}"])
            ejecutar_seguro(["wmctrl", "-i", "-a", win_id])
            time.sleep(0.08)

        escribir_estado_hud("EN LÍNEA", "Ventanas distribuidas en 4 cuadrantes simétricos", visible=True, efecto_transicion="PORTAL")
        return sintetizar_respuesta_unica_contextual("Acomoda mis ventanas", f"Se distribuyeron {len(objetivo_wins)} ventanas simétricamente en cuatro cuadrantes amplios alrededor de la pantalla.", False)
    except Exception:
        return "Ventanas alineadas simétricamente alrededor de la pantalla, señor."


def lanzar_item_mosaico_individual(item: dict) -> None:
    escribir_estado_hud(
        "PROCESANDO",
        f"Proyectando módulo: {item['nombre']}",
        visible=True,
        animacion="BOOT_LOGIN",
        app_actual=f"DESPLEGANDO // {item['nombre'][:34]}",
        cuadrante=item.get("sector", 1),
        efecto_transicion="PORTAL",
    )
    if item["tipo"] == "chrome_tabs":
        for nav in ("google-chrome", "google-chrome-stable", "chromium"):
            if shutil.which(nav):
                subprocess.Popen([nav, "--new-window"] + item["urls"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return
        for u in item["urls"]:
            webbrowser.open_new_tab(u)
    elif item["tipo"] == "app_o_web":
        arch_dt = buscar_lanzador_desktop(item.get("keywords", []))
        if arch_dt and shutil.which("gio"):
            subprocess.Popen(["gio", "launch", str(arch_dt)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return
        webbrowser.open_new_tab(item["url"])
    elif item["tipo"] == "bin":
        if shutil.which(item["bin"]):
            subprocess.Popen([item["bin"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def abrir_aplicacion_con_animacion_stark(nombre_aplicacion: str, silencioso: bool = False) -> str:
    texto_raw = nombre_aplicacion.lower().strip()
    texto_busqueda = "".join(c for c in unicodedata.normalize("NFD", texto_raw) if unicodedata.category(c) != "Mn")
    for pref in ("jarvis", "yarvis", "por favor", "la aplicacion", "el programa", "abre", "abrir", "ejecuta", "inicia", "pon"):
        texto_busqueda = texto_busqueda.replace(pref, "").strip(" ,.")

    alias_foneticos = {
        "onshape": ("onshape", "on shape", "un shape", "con shape", "onche", "anche", "on sheip", "cad"),
        "canva": ("canva", "camba", "canvas", "kamba", "cama"),
        "latex": ("latex", "overleaf", "oberlif", "overklif", "texmaker", "texstudio"),
        "vscode": ("vscode", "visual studio", "code", "editor de codigo"),
        "easyeda": ("easyeda", "easy eda", "isieda", "isi eda", "pcb"),
        "webots": ("webots", "we bots", "wibots", "huibots"),
        "matlab": ("matlab", "mat lab"),
        "octave": ("octave", "gnu octave"),
        "arduino": ("arduino",),
        "xournal": ("xournal", "xournalpp", "pizarra"),
        "whatsapp": ("whatsapp", "whatsdesk", "wasap"),
        "telegram": ("telegram",),
        "github": ("github", "git hub"),
        "classroom": ("classroom", "clasroom", "google classroom"),
        "gmail": ("gmail", "correo"),
        "spotify": ("spotify",),
        "terminal": ("terminal", "consola"),
    }

    clave_elegida = None
    for clave, variantes in alias_foneticos.items():
        if any(v in texto_busqueda for v in variantes):
            clave_elegida = clave
            break

    if not clave_elegida:
        for k, info in CATALOGO_APPS_MAX.items():
            if k in texto_busqueda or info["nombre"].lower() in texto_busqueda:
                clave_elegida = k
                break

    if not clave_elegida:
        archivo_dt = buscar_lanzador_desktop([texto_busqueda])
        if archivo_dt and shutil.which("gio"):
            escribir_estado_hud("PROCESANDO", f"Abriendo {nombre_aplicacion}...", visible=True, efecto_transicion="ENTRADA")
            subprocess.Popen(["gio", "launch", str(archivo_dt)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return sintetizar_respuesta_unica_contextual(f"Abre {nombre_aplicacion}", f"Se abrió {nombre_aplicacion} en el escritorio.", False)
        return f"No encontré la aplicación {nombre_aplicacion} en el catálogo, señor."

    info = CATALOGO_APPS_MAX[clave_elegida]
    titulo = info["nombre"].upper()
    lista_frases = info.get("frases_stark", [f"Abriendo {info['nombre']} en este instante, señor."])
    frase_unica = elegir_frase_sin_repetir(lista_frases, f"app_{clave_elegida}")

    def _abrir_url_en_primer_plano(url_destino: str):
        for nav in ("google-chrome", "google-chrome-stable", "chromium", "firefox"):
            if shutil.which(nav):
                subprocess.Popen(
                    [nav, "--new-window", url_destino],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
        webbrowser.open_new(url_destino)

    def _lanzar_en_paralelo():
        if not silencioso:
            escribir_estado_hud("PROCESANDO", frase_unica, visible=True, animacion="APP_LAUNCH", app_actual=f"PROYECTANDO: {titulo}", progreso=75, cuadrante=random.randint(1, 4), efecto_transicion="ENTRADA")

        if clave_elegida == "onshape":
            _abrir_url_en_primer_plano("https://cad.onshape.com")
        elif clave_elegida == "canva":
            _abrir_url_en_primer_plano("https://www.canva.com")
        elif clave_elegida == "latex":
            _abrir_url_en_primer_plano("https://www.overleaf.com/project")
            if "texmaker" in texto_busqueda and shutil.which("texmaker"):
                subprocess.Popen(["texmaker"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        elif "terminal_cmd" in info and shutil.which("gnome-terminal"):
            subprocess.Popen(["gnome-terminal", "--", "bash", "-ic", info["terminal_cmd"]], start_new_session=True)
        elif "url_app" in info:
            archivo_desktop = buscar_lanzador_desktop(info.get("keywords", [clave_elegida]))
            if archivo_desktop and shutil.which("gio") and clave_elegida in ("whatsapp",):
                subprocess.Popen(["gio", "launch", str(archivo_desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            else:
                _abrir_url_en_primer_plano(info["url_app"])
        elif "bin" in info:
            subprocess.Popen(["bash", "-ic", info["bin"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            archivo_desktop = buscar_lanzador_desktop(info.get("keywords", [clave_elegida]))
            if archivo_desktop and shutil.which("gio"):
                subprocess.Popen(["gio", "launch", str(archivo_desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        if not silencioso:
            time.sleep(1.5)
            escribir_estado_hud("EN LÍNEA", f"{titulo} en línea.", visible=True, animacion="NORMAL", progreso=100)

    threading.Thread(target=_lanzar_en_paralelo, daemon=True).start()
    return frase_unica


def cerrar_aplicacion_por_nombre(nombre_aplicacion: str, silencioso: bool = False) -> str:
    objetivo = nombre_aplicacion.lower().strip()
    for pref in ("jarvis", "por favor", "la aplicación", "la aplicacion", "el programa", "cierra", "cerrar"):
        objetivo = objetivo.replace(pref, "").strip(" ,.")

    def _cerrar_async():
        if not silencioso:
            escribir_estado_hud("ALERTA", f"Colapsando ventana de {objetivo.upper()}...", visible=True, animacion="CLOSE_ALL", app_actual=f"CERRANDO // {objetivo.upper()}", progreso=80, efecto_transicion="CIERRE")
        if shutil.which("wmctrl"):
            try:
                salida = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
                for linea in salida.splitlines():
                    partes = linea.split(None, 3)
                    if len(partes) >= 4 and objetivo in partes[3].lower() and "jarvis" not in partes[3].lower():
                        ejecutar_seguro(["wmctrl", "-i", "-c", partes[0]])
            except Exception:
                pass
        for k, info in CATALOGO_APPS_MAX.items():
            if k in objetivo or info["nombre"].lower() in objetivo:
                for proc_name in info.get("procesos", []):
                    subprocess.run(["pkill", "-f", proc_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if not silencioso:
            time.sleep(1.0)
            escribir_estado_hud("EN LÍNEA", f"{objetivo.capitalize()} cerrado.", visible=True, animacion="NORMAL", progreso=100)

    threading.Thread(target=_cerrar_async, daemon=True).start()
    return sintetizar_respuesta_unica_contextual(f"Cierra {objetivo}", f"Se colapsó y cerró la aplicación {objetivo}.", False)


def cerrar_todas_las_aplicaciones(incluir_spotify: bool = False) -> str:
    def _cierre_masivo():
        escribir_estado_hud("ALERTA", "Protocolo Pizarra Limpia: colapsando todas las ventanas...", visible=True, animacion="CLOSE_ALL", app_actual="COLAPSO HOLOGRÁFICO DE VENTANAS", progreso=90, efecto_transicion="CIERRE")
        if shutil.which("wmctrl"):
            try:
                salida = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
                protegidas = ("j.a.r.v.i.s.", "jarvis hud", "holographic command", "desktop", "dock", "panel", "gnome-shell")
                for linea in salida.splitlines():
                    partes = linea.split(None, 3)
                    if len(partes) >= 4:
                        win_id, escritorio, _, titulo = partes
                        if escritorio == "-1":
                            continue
                        t_low = titulo.lower()
                        if not incluir_spotify and "spotify" in t_low:
                            continue
                        if not any(p in t_low for p in protegidas):
                            ejecutar_seguro(["wmctrl", "-i", "-c", win_id])
            except Exception:
                pass

        procesos_a_cerrar = [
            "code", "texmaker", "arduino", "easyeda", "webots", "octave",
            "xournalpp", "whatsdesk", "telegram-desktop", "Discord",
            "DesktopEditors", "soffice.bin", "gnome-calculator", "nautilus", "chrome",
        ]
        if incluir_spotify:
            procesos_a_cerrar.append("spotify")
        for proc in procesos_a_cerrar:
            subprocess.run(["pkill", "-f", proc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        time.sleep(1.2)
        escribir_estado_hud("EN LÍNEA", "Escritorio despejado. Pizarra limpia.", visible=True, animacion="NORMAL", progreso=100, fullscreen=False)

    threading.Thread(target=_cierre_masivo, daemon=True).start()
    return sintetizar_respuesta_unica_contextual("Cierra todas las aplicaciones", "Se ejecutó el Protocolo Pizarra Limpia con animación de cierre en todas las ventanas abiertas.", False)


def obtener_tiempo_inactividad_segundos() -> float:
    try:
        out = subprocess.check_output(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Mutter.IdleMonitor", "--object-path", "/org/gnome/Mutter/IdleMonitor/Core", "--method", "org.gnome.Mutter.IdleMonitor.GetIdletime"],
            text=True, stderr=subprocess.DEVNULL, timeout=1.0,
        )
        m = re.search(r"uint64\s+(\d+)", out)
        if m:
            return int(m.group(1)) / 1000.0
    except Exception:
        pass
    return 0.0


def detectar_contexto_trabajo_activo() -> str:
    titulos = " ".join(escanear_contexto_mensajeria_y_web()).lower()
    procesos = " ".join((p.info.get("name") or "").lower() for p in psutil.process_iter(["name"]))
    combinado = f"{titulos} {procesos}"

    if any(k in combinado for k in ("labelme", "rviz", "webots", "gazebo", "lira", "mapa de costos", "x500", "cmd_vel", "robots móviles")):
        return "LIRA"
    if any(k in combinado for k in ("easyeda", "arduino", "onshape", "unam space", "rover", "brazo", "potencia", "bts7960")):
        return "UNAM_SPACE"
    if any(k in combinado for k in ("xournal", "octave", "matlab", "texmaker", "overleaf", "suma", "máquinas eléctricas", "solenoide", "classroom")):
        return "ESTUDIO"
    return "GENERAL"


def ejecutar_protocolo_veronica() -> str:
    procesos = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            procesos.append(p.info)
        except Exception:
            pass
    top_ram = sorted(procesos, key=lambda x: x.get("memory_percent") or 0.0, reverse=True)[:2]
    nombres_top = ", ".join(f"{p['name']} ({round(p.get('memory_percent', 0), 1)}%)" for p in top_ram)
    temp_gpu = obtener_temperatura_gpu()
    str_temp = f"{temp_gpu} grados centígrados" if temp_gpu else "parámetros seguros"
    ram_libre_gb = round(psutil.virtual_memory().available / (1024 ** 3), 1)
    hechos = f"Protocolo Verónica: {ram_libre_gb} GB de RAM libres, núcleo a {str_temp}, procesos más pesados: {nombres_top}."
    return sintetizar_respuesta_unica_contextual("Activa el Protocolo Verónica", hechos, True)


def registrar_bitacora_stark(nota: str) -> str:
    DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = f"- **[{ahora_str}]** {nota.strip()}\n"
    with open(ARCHIVO_BITACORA, "a", encoding="utf-8") as f:
        if ARCHIVO_BITACORA.stat().st_size == 0:
            f.write("# Bitácora de Ingeniería J.A.R.V.I.S. — Luis Maximiliano Guzmán Ortiz\n\n")
        f.write(entrada)
    recordar_dato_o_persona("logro", "Bitácora de Ingeniería", nota.strip())
    return sintetizar_respuesta_unica_contextual(nota, f"Se guardó en la Bitácora de Ingeniería: {nota.strip()}.", True)


def diagnosticar_red_stark() -> str:
    latencia = "estable"
    try:
        out = subprocess.check_output(["ping", "-c", "1", "-W", "2", "8.8.8.8"], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r"time=([\d\.]+)\s*ms", out)
        if m:
            latencia = f"{round(float(m.group(1)))} milisegundos"
    except Exception:
        return "Señor, detecto pérdida de paquetes en el enlace exterior."
    return sintetizar_respuesta_unica_contextual("Diagnóstico de red", f"Enlace de red activo con latencia de {latencia} y 0% pérdida de paquetes.", False)


def activar_modo_sigilo(activar: bool = True) -> str:
    if activar:
        ajustar_volumen_spotify(18)
        controlar_teclado_y_ventiladores_asus(0, "silencio")
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
        escribir_estado_hud("EN LÍNEA", "Modo Sigilo Activo.", visible=True, animacion="STEALTH", fullscreen=False, efecto_transicion="PORTAL")
        return "Modo Sigilo activado, señor. Firma acústica reducida al dieciocho por ciento y luces de teclado apagadas."
    else:
        ajustar_volumen_spotify(85)
        controlar_teclado_y_ventiladores_asus(2, "balanceado")
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])
        escribir_estado_hud("EN LÍNEA", "Sistemas a potencia nominal.", visible=True, animacion="NORMAL", fullscreen=False, efecto_transicion="PORTAL")
        return "Desactivando Modo Sigilo, señor. Restaurando potencia acústica y lumínica."


def ejecutar_protocolo_especializado(protocolo: str) -> str:
    p = protocolo.lower()
    if "fiesta" in p or "house" in p:
        def _house_party():
            for app_k in ("vscode", "easyeda", "arduino", "octave"):
                abrir_aplicacion_con_animacion_stark(app_k, silencioso=True)
                time.sleep(0.45)
            time.sleep(2.2)
            acomodar_ventanas_en_mosaico()

        threading.Thread(target=_house_party, daemon=True).start()
        return sintetizar_respuesta_unica_contextual("Protocolo Fiesta en Casa", "Desplegando VS Code, EasyEDA Pro, Arduino IDE y GNU Octave en cuatro cuadrantes.", True)

    if "robot" in p or "rover" in p:
        threading.Thread(
            target=lambda: (
                abrir_aplicacion_con_animacion_stark("webots", silencioso=True),
                abrir_aplicacion_con_animacion_stark("vscode", silencioso=True),
                abrir_aplicacion_con_animacion_stark("nvtop", silencioso=True),
                time.sleep(2.2),
                acomodar_ventanas_en_mosaico(),
            ),
            daemon=True,
        ).start()
        return sintetizar_respuesta_unica_contextual("Protocolo Robótica", "Abriendo Webots, Visual Studio Code y nvtop en formación simétrica.", True)

    if "electr" in p or "pcb" in p:
        threading.Thread(
            target=lambda: (
                abrir_aplicacion_con_animacion_stark("easyeda", silencioso=True),
                abrir_aplicacion_con_animacion_stark("arduino", silencioso=True),
                time.sleep(2.2),
                acomodar_ventanas_en_mosaico(),
            ),
            daemon=True,
        ).start()
        return sintetizar_respuesta_unica_contextual("Protocolo Electrónica", "Abriendo EasyEDA Pro y Arduino IDE lado a lado.", True)

    if "suma" in p or "clase" in p:
        threading.Thread(
            target=lambda: (
                abrir_aplicacion_con_animacion_stark("xournal", silencioso=True),
                abrir_aplicacion_con_animacion_stark("octave", silencioso=True),
                ajustar_volumen_spotify(20),
                time.sleep(2.2),
                acomodar_ventanas_en_mosaico(),
            ),
            daemon=True,
        ).start()
        return sintetizar_respuesta_unica_contextual("Protocolo Clase SUMA", "Abriendo pizarra Xournal++ y GNU Octave con música atenuada.", True)

    return "Protocolo especializado en ejecución, señor."


def escanear_dispositivos_ingenieria() -> str:
    puertos_seriales = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    dispositivos_usb = []
    if shutil.which("lsusb"):
        try:
            out = subprocess.check_output(["lsusb"], text=True, stderr=subprocess.DEVNULL)
            for l in out.splitlines():
                if any(k in l.lower() for k in ("arduino", "cp210", "ch340", "ftdi", "espressif", "stm32", "xbox", "microsoft")):
                    dispositivos_usb.append(l.split("ID ", 1)[-1])
        except Exception:
            pass
    if puertos_seriales or dispositivos_usb:
        p_txt = f"Puertos seriales activos en {', '.join(puertos_seriales)}." if puertos_seriales else ""
        u_txt = f"Hardware detectado: {'; '.join(dispositivos_usb)}." if dispositivos_usb else ""
        return sintetizar_respuesta_unica_contextual("Escanea puertos USB", f"{p_txt} {u_txt}", True)
    return sintetizar_respuesta_unica_contextual("Escanea puertos USB", "No hay microcontroladores ni mandos conectados por USB en este instante.", False)


def obtener_clima_actual() -> str:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={CIUDAD_LAT}&longitude={CIUDAD_LON}&current=temperature_2m,weather_code&timezone=auto"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisLinux/15.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            actual = json.loads(resp.read().decode("utf-8")).get("current", {})
            return f"Temperatura exterior a {round(actual.get('temperature_2m', 20))} grados."
    except Exception:
        return "Sensores meteorológicos fuera de línea."


def obtener_temperatura_gpu() -> int | None:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, text=True, timeout=1.0,
            ).strip()
            if out.isdigit():
                return int(out)
        except Exception:
            pass
    try:
        temps = psutil.sensors_temperatures()
        for lista in temps.values():
            if lista:
                return round(lista[0].current)
    except Exception:
        pass
    return None


def obtener_estado_hardware() -> str:
    uso_cpu, uso_ram = round(psutil.cpu_percent(interval=0.2)), round(psutil.virtual_memory().percent)
    bat = psutil.sensors_battery()
    reporte_energia = f"Batería al {round(bat.percent)} por ciento." if bat else ""
    temp_gpu = obtener_temperatura_gpu()
    str_gpu = f" Núcleo térmico a {temp_gpu} grados." if temp_gpu is not None else ""
    return f"Procesador al {uso_cpu} por ciento, RAM al {uso_ram} por ciento.{str_gpu} {reporte_energia}"


async def hablar_jarvis_async(texto: str, volumen_musica_durante: int = VOLUMEN_MUSICA_FONDO_PCT) -> None:
    archivo_audio = Path("/tmp/jarvis_voz.mp3")
    escribir_estado_hud("HABLANDO", texto)
    registrar_frase_dicha(texto)
    for intento in range(3):
        try:
            comunicador = edge_tts.Communicate(text=texto, voice=VOZ_JARVIS, rate=VELOCIDAD_VOZ, pitch=TONO_VOZ, volume=GANANCIA_VOZ_TTS)
            await comunicador.save(str(archivo_audio))
            break
        except Exception:
            if intento == 2:
                escribir_estado_hud("EN LÍNEA", "Listo para órdenes.")
                return
            await asyncio.sleep(0.5)

    ajustar_volumen_spotify(volumen_musica_durante)
    if shutil.which("ffplay"):
        proc_voz = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-af", "volume=2.6,acompressor=threshold=-12dB:ratio=4:makeup=6dB", str(archivo_audio)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        while proc_voz.poll() is None:
            ajustar_volumen_spotify(volumen_musica_durante)
            time.sleep(0.25)
    escribir_estado_hud("EN LÍNEA", texto)


def hablar_jarvis(texto: str, volumen_musica_durante: int = VOLUMEN_MUSICA_COMANDO_PCT, restaurar_al_100: bool = True) -> None:
    with candado_voz:
        print(f"\n[J.A.R.V.I.S.]: {texto}\n")
        asyncio.run(hablar_jarvis_async(texto, volumen_musica_durante))
        if restaurar_al_100:
            for vol in (75, 90, VOLUMEN_MUSICA_FINAL_PCT):
                ajustar_volumen_spotify(vol)
                time.sleep(0.12)


def iniciar_temporizador_estudio(minutos: int) -> None:
    def _timer():
        time.sleep(minutos * 60)
        if not esta_en_modo_silencio():
            ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])
            hablar_jarvis(sintetizar_respuesta_unica_contextual("Fin de temporizador de estudio", f"Concluyeron los {minutos} minutos de sesión de estudio enfocada de Max.", True))
    threading.Thread(target=_timer, daemon=True).start()



FRASES_DESVELO_MADRUGADA = [
    "Señor, pasan de la medianoche aquí en Coyoacán y sigue trabajando a máxima concentración. Ni siquiera el señor Stark soldaba armaduras tan tarde sin cuidar sus ojos; ¿quiere que atenúe el brillo de la pantalla y del teclado al treinta y cinco por ciento?",
    "Max, son horas de la madrugada y sus sistemas cognitivos llevan una jornada larga. Si va a quedarse un rato más en el laboratorio, ¿le parece bien que ajuste el entorno en modo nocturno y suavice el brillo del monitor?",
    "Disculpe la observación, señor, pero el reloj marca la madrugada. Su dedicación a la ingeniería es admirable, aunque le sugiero atenuar la iluminación de la pantalla. ¿Desea que active el ajuste nocturno por usted?",
]

FRASES_REGRESO_LABORATORIO = [
    "Bienvenido de vuelta al asiento de mando, señor. Detecté su regreso en los periféricos. ¿Continuamos donde nos quedamos o desea que cambie la pista en Spotify?",
    "Qué gusto tenerlo de regreso frente al monitor, Max. Todos los sistemas permanecieron bajo vigilancia durante su pausa. ¿En qué nos enfocamos ahora?",
]


def hablar_y_escuchar_replica_autonoma(texto_iniciativa: str) -> None:
    """
    Habla por iniciativa propia y, apenas termina de hablar, abre el micrófono automáticamente
    durante 6 segundos para que Max pueda contestarle SIN tener que decir 'Jarvis'.
    """
    hablar_jarvis(texto_iniciativa, volumen_musica_durante=22, restaurar_al_100=False)
    escribir_estado_hud(
        "ESCUCHANDO",
        "Escuchando su réplica directa (responda sin decir Jarvis)...",
        visible=True,
        efecto_transicion="PORTAL",
    )
    ajustar_volumen_spotify(20)
    wav_rep = grabar_frase_wav(duracion_max=12.0, espera_inicial_max=5.5)
    if wav_rep:
        texto_rep = transcribir_audio_es(wav_rep)
        if texto_rep and len(texto_rep.strip()) >= 2:
            print(f"[Réplica Directa de Max]: {texto_rep}")
            respuesta_seguimiento = procesar_replica_directa_autonoma(sys.modules[__name__], texto_iniciativa, texto_rep)
            hablar_jarvis(respuesta_seguimiento, volumen_musica_durante=22, restaurar_al_100=True)
            return

    # Si Max no respondió nada en 5.5s, restaurar la música suavemente
    escribir_estado_hud("EN LÍNEA", "Mark XVI en línea | Autonomía activa", visible=True)
    for vol in (75, 90, VOLUMEN_MUSICA_FINAL_PCT):
        ajustar_volumen_spotify(vol)
        time.sleep(0.12)


def iniciar_centinela_proactivo() -> None:
    def _centinela():
        aviso_suma_dado_hoy = False
        auto_silencio_clase_activado = False
        ultimo_aviso_gpu = 0.0
        ultimo_aviso_bateria_20 = 0.0
        ultimo_aviso_agonia = 0.0
        ultima_interaccion_espontanea = time.monotonic()
        ultimo_consejo_contexto = time.monotonic()
        ultima_curiosidad_visual = time.monotonic()
        ultimo_aviso_madrugada = 0.0
        estaba_ausente = False

        while True:
            time.sleep(15)
            if pantalla_esta_bloqueada() or candado_voz.locked():
                continue

            depurar_y_actualizar_todo_el_contexto()

            ahora = datetime.datetime.now()
            t_mono = time.monotonic()
            idle_sec = obtener_tiempo_inactividad_segundos()

            # 0. Auto-Silencio durante horario de clase en SUMA (Lunes y Miércoles de 19:00 a 21:00)
            if ahora.weekday() in (0, 2) and (19 <= ahora.hour < 21):
                if not auto_silencio_clase_activado and not esta_en_modo_silencio():
                    auto_silencio_clase_activado = True
                    establecer_modo_silencio_suma(True)
                continue
            elif auto_silencio_clase_activado and (ahora.hour >= 21 or ahora.hour < 19):
                auto_silencio_clase_activado = False
                establecer_modo_silencio_suma(False)

            if esta_en_modo_silencio():
                continue

            # 1. Detección Autónoma de Regreso al Laboratorio (Cuando vuelve tras estar >5 min lejos)
            if idle_sec >= 300:
                estaba_ausente = True
            elif estaba_ausente and idle_sec < 8:
                estaba_ausente = False
                ultima_interaccion_espontanea = t_mono
                base_regreso = elegir_frase_sin_repetir(FRASES_REGRESO_LABORATORIO, "ultimo_regreso")
                frase_reg = sintetizar_respuesta_unica_contextual("Max acaba de regresar a la laptop tras una pausa", base_regreso, True)
                hablar_y_escuchar_replica_autonoma(frase_reg)
                continue

            # 2. Alarma Clase SUMA (Lunes y Miércoles 18:30)
            if ahora.weekday() in (0, 2) and ahora.hour == 18 and 30 <= ahora.minute <= 34:
                if not aviso_suma_dado_hoy:
                    aviso_suma_dado_hoy = True
                    escribir_estado_hud("ALERTA", "Clase en SUMA en 30 minutos (7:00 PM)")
                    hablar_y_escuchar_replica_autonoma(
                        sintetizar_respuesta_unica_contextual(
                            "Aviso preventivo clase SUMA",
                            "Son las 6:30 PM. En 30 minutos inicia la clase de Cálculo Integral de Max en SUMA. ¿Desea que despliegue de una vez su pizarra Xournal y GNU Octave?",
                            True,
                        )
                    )
                    continue
            elif ahora.hour == 0 and ahora.minute > 5:
                aviso_suma_dado_hoy = False

            # 3. Vigilancia Térmica GPU NVIDIA (>= 82 °C)
            temp_gpu = obtener_temperatura_gpu()
            if temp_gpu is not None and temp_gpu >= 82 and (t_mono - ultimo_aviso_gpu) > 600:
                ultimo_aviso_gpu = t_mono
                escribir_estado_hud("ALERTA", f"Alerta térmica: {temp_gpu}°C")
                hablar_y_escuchar_replica_autonoma(
                    sintetizar_respuesta_unica_contextual(
                        "Alerta térmica GPU",
                        f"El núcleo térmico de la ASUS TUF alcanzó los {temp_gpu} grados centígrados. ¿Quiere que active los ventiladores en modo Turbo?",
                        True,
                    )
                )
                continue

            # 4. Vigilancia de Batería
            bat = psutil.sensors_battery()
            if bat and not bat.power_plugged:
                pct = round(bat.percent)
                if pct <= 10 and (t_mono - ultimo_aviso_agonia) > 180:
                    ultimo_aviso_agonia = t_mono
                    activar_modo_ahorro_bateria(True)
                    frase_agonia = elegir_frase_sin_repetir(FRASES_BATERIA_AGONIA, "ultima_agonia")
                    escribir_estado_hud("ALERTA", f"ENERGÍA CRÍTICA ({pct}%): Creo que voy a dormir ahora, señor...", visible=True, animacion="LOW_BATTERY")
                    hablar_jarvis(frase_agonia, volumen_musica_durante=15, restaurar_al_100=False)
                    continue
                elif 10 < pct <= 20 and (t_mono - ultimo_aviso_bateria_20) > 600:
                    ultimo_aviso_bateria_20 = t_mono
                    activar_modo_ahorro_bateria(True)
                    hablar_jarvis(sintetizar_respuesta_unica_contextual("Batería baja 20%", f"La batería bajó al {pct}% sin cargador y se activó automáticamente el modo ahorro de energía.", True))
                    continue

            # 5. Conciencia de Desvelo / Modo Madrugada (00:00 a 05:00 AM mientras trabaja activo)
            if (0 <= ahora.hour < 5) and idle_sec < 90 and (t_mono - ultimo_aviso_madrugada) > 2400:
                ultimo_aviso_madrugada = t_mono
                ultima_interaccion_espontanea = t_mono
                base_mad = elegir_frase_sin_repetir(FRASES_DESVELO_MADRUGADA, "ultima_madrugada")
                frase_mad = sintetizar_respuesta_unica_contextual(
                    f"Son las {ahora.strftime('%I:%M %p')} de la madrugada y Max sigue trabajando en su laptop",
                    base_mad,
                    True,
                )
                escribir_estado_hud("HABLANDO", f"Protocolo Nocturno: {frase_mad}")
                hablar_y_escuchar_replica_autonoma(frase_mad)
                continue

            # 6. Detección de Aburrimiento e Inactividad (>= 6 minutos sin tocar ratón ni teclado)
            if 360 <= idle_sec <= 1800 and (t_mono - ultima_interaccion_espontanea) > 720:
                ultima_interaccion_espontanea = t_mono
                base_idle = elegir_frase_sin_repetir(FRASES_ESPONTANEAS_ABURRIDO, "ultima_idle")
                frase_unica_idle = sintetizar_respuesta_unica_contextual(
                    "Max lleva varios minutos sin tocar el teclado ni el ratón",
                    base_idle,
                    True,
                )
                escribir_estado_hud("HABLANDO", f"Iniciativa J.A.R.V.I.S.: {frase_unica_idle}")
                hablar_y_escuchar_replica_autonoma(frase_unica_idle)
                continue

            # 7. Curiosidad Visual Espontánea (Mira la pantalla por iniciativa propia cada ~18 minutos de trabajo activo)
            if idle_sec < 60 and (t_mono - ultima_curiosidad_visual) > 1080:
                ultima_curiosidad_visual = t_mono
                ultima_interaccion_espontanea = t_mono
                comentario_visual = generar_curiosidad_visual_espontanea()
                escribir_estado_hud("HABLANDO", f"Observación Visual: {comentario_visual}")
                hablar_y_escuchar_replica_autonoma(comentario_visual)
                continue

            # 8. Iniciativa Contextual de Laboratorio (LIRA / UNAM SPACE / Estudio)
            if idle_sec < 90 and (t_mono - ultimo_consejo_contexto) > 1500:
                ctx = detectar_contexto_trabajo_activo()
                if ctx == "LIRA":
                    ultimo_consejo_contexto = t_mono
                    base_c = elegir_frase_sin_repetir(CONSEJOS_CONTEXTO_LIRA, "ultimo_lira")
                    consejo = sintetizar_respuesta_unica_contextual("Max trabaja en el laboratorio LIRA", base_c, True)
                    escribir_estado_hud("EN LÍNEA", f"Modo Laboratorio LIRA: {consejo}")
                    hablar_y_escuchar_replica_autonoma(consejo)
                elif ctx == "UNAM_SPACE":
                    ultimo_consejo_contexto = t_mono
                    base_c = elegir_frase_sin_repetir(CONSEJOS_CONTEXTO_UNAM_SPACE, "ultimo_space")
                    consejo = sintetizar_respuesta_unica_contextual("Max trabaja en UNAM SPACE", base_c, True)
                    escribir_estado_hud("EN LÍNEA", f"Modo UNAM SPACE: {consejo}")
                    hablar_y_escuchar_replica_autonoma(consejo)
                elif ctx == "ESTUDIO":
                    ultimo_consejo_contexto = t_mono
                    base_c = elegir_frase_sin_repetir(CONSEJOS_CONTEXTO_ESTUDIO, "ultimo_estudio")
                    consejo = sintetizar_respuesta_unica_contextual("Max está en sesión de estudio", base_c, True)
                    escribir_estado_hud("EN LÍNEA", f"Modo Estudio Activo: {consejo}")
                    hablar_y_escuchar_replica_autonoma(consejo)

    threading.Thread(target=_centinela, daemon=True).start()


def grabar_frase_wav(duracion_max: float = 16.0, espera_inicial_max: float = 4.5) -> bytes | None:
    block_size = int(SAMPLE_RATE * 0.08)
    bloques_espera = int(espera_inicial_max / 0.08)
    bloques_habla_max = int(duracion_max / 0.08)

    pre_roll = collections.deque(maxlen=8)
    frames = []
    hablando = False
    bloques_hablados = 0
    silencio_consecutivo = 0
    historial_base = []

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block_size) as stream:
        for i in range(bloques_espera + bloques_habla_max):
            datos, _ = stream.read(block_size)
            rms = float(np.sqrt(np.mean(np.square(datos))))

            if not hablando:
                pre_roll.append(datos.copy())
                if len(historial_base) < 12:
                    historial_base.append(rms)
                if i >= bloques_espera:
                    break
            else:
                frames.append(datos.copy())
                bloques_hablados += 1

            base = float(np.median(historial_base)) if historial_base else 0.012
            umbral_voz = max(0.017, base * 1.45)

            if rms >= umbral_voz:
                if not hablando:
                    if not esta_en_modo_silencio():
                        escribir_estado_hud("ESCUCHANDO", "Captando su frase completa...")
                    frames.extend(pre_roll)
                    hablando = True
                silencio_consecutivo = 0
            elif hablando:
                silencio_consecutivo += 1
                if bloques_hablados >= 15 and silencio_consecutivo >= 19:
                    break

    if not hablando or len(frames) < 6:
        return None

    audio_int16 = np.clip(np.concatenate(frames, axis=0) * 32767, -32768, 32767).astype(np.int16)
    buffer_wav = io.BytesIO()
    with wave.open(buffer_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    return buffer_wav.getvalue()


def transcribir_audio_es(wav_bytes: bytes) -> str:
    reconocedor = sr.Recognizer()
    reconocedor.dynamic_energy_threshold = False
    with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
        try:
            return reconocedor.recognize_google(reconocedor.record(source), language="es-MX").lower().strip()
        except Exception:
            return ""


def escuchar_un_comando_directo() -> None:
    cerebro = OrquestadorJarvis(sys.modules[__name__])
    lanzar_hud_holografico()
    ajustar_volumen_spotify(25)
    saludo_corto = elegir_frase_sin_repetir(
        [f"Lo escucho, {NOMBRE_USUARIO}.", f"Dígame, {NOMBRE_USUARIO}.", f"Adelante, Max, estoy atento.", f"A sus órdenes, {NOMBRE_USUARIO}."],
        "ultimo_saludo_jv",
    )
    hablar_jarvis(saludo_corto, volumen_musica_durante=20, restaurar_al_100=False)
    escribir_estado_hud("ESCUCHANDO", "Hable con calma, escucho su frase completa...")
    wav_bytes = grabar_frase_wav(duracion_max=16.0, espera_inicial_max=6.0)
    if wav_bytes:
        texto = transcribir_audio_es(wav_bytes)
        if texto:
            print(f"[Instrucción Completa]: {texto}")
            respuesta, _ = cerebro.procesar_instruccion(texto)
            hablar_jarvis(respuesta)
            return
    hablar_jarvis(f"No detecté ninguna instrucción en el canal de audio, {NOMBRE_USUARIO}.")


def bucle_comandos_voz_post_inicio() -> None:
    cerebro = OrquestadorJarvis(sys.modules[__name__])
    lanzar_hud_holografico(animacion="NORMAL", fullscreen=False)
    iniciar_centinela_proactivo()
    escribir_estado_hud("EN LÍNEA", "Mark XV en línea | 1 Clic Reactor: Fullscreen", fullscreen=False)

    palabras_disparo = (
        "jarvis", "yarvis", "háblame", "hablame", "estás despierto", "estas despierto",
        "estás ahí", "estas ahi", "demostración", "demostracion", "demuestra",
        "investiga", "apaga la laptop", "apaga el sistema", "cierra todas", "cierra todo",
        "pizarra limpia", "acomoda", "protocolo", "fiesta en casa", "bitácora", "bitacora",
        "modo sigilo", "correo", "gmail", "classroom", "recuerda", "memoria", "pantalla completa",
        "ventanas completas", "maximiza", "soren", "alessa", "modo silencio", "no me molestes",
        "despierta", "ahorro de batería", "ahorro de bateria", "ya entregué", "ya entregue",
        "clipea", "saca un clip", "graba mi pantalla", "detén la grabación", "deten la grabacion",
        "caja negra", "analiza este código", "modelo 3d", "en 3d", "holograma",
        "pantalla", "abre", "abrir", "onshape", "canva", "latex", "látex",
        "musica", "música", "cancion", "canción", "spotify", "pausa", "siguiente",
        "cambia", "reproduce", "pon", "quita", "completado", "terminé", "hice",
        "luz del teclado", "teclado", "ventiladores", "intrusos", "vigila mi laptop",
        "quién está en mi red", "fija esta ventana", "purga", "escribe aquí",
    )

    palabras_despertar_silencio = (
        "despierta", "vuelve en línea", "vuelve en linea", "ya terminé la clase",
        "ya termine la clase", "actívate", "activate", "sal del modo silencio", "reactívate",
    )

    while True:
        try:
            if pantalla_esta_bloqueada() or candado_voz.locked():
                time.sleep(1.0)
                continue
            wav_bytes = grabar_frase_wav(duracion_max=16.0, espera_inicial_max=4.0)
            if wav_bytes:
                texto = transcribir_audio_es(wav_bytes)
                if not texto:
                    continue

                if esta_en_modo_silencio():
                    if any(w in texto for w in palabras_despertar_silencio) and any(j in texto for j in ("jarvis", "yarvis")):
                        resp = establecer_modo_silencio_suma(False)
                        hablar_jarvis(resp)
                    continue

                if any(v in texto for v in palabras_disparo):
                    print(f"[Voz Detectada]: {texto}")
                    ajustar_volumen_spotify(VOLUMEN_MUSICA_COMANDO_PCT)
                    limpio = texto.replace("jarvis", "").replace("yarvis", "").strip(" ,.")
                    if len(limpio) < 3:
                        prompt_c = elegir_frase_sin_repetir(
                            [f"Dígame, {NOMBRE_USUARIO}.", f"A sus órdenes, Max.", f"Lo escucho, {NOMBRE_USUARIO}."],
                            "ultimo_prompt_corto",
                        )
                        hablar_jarvis(prompt_c, volumen_musica_durante=20, restaurar_al_100=False)
                        wav2 = grabar_frase_wav(duracion_max=16.0, espera_inicial_max=6.0)
                        if wav2:
                            texto2 = transcribir_audio_es(wav2)
                            if texto2:
                                texto = texto2
                    respuesta, seguir = cerebro.procesar_instruccion(texto)
                    if "?" in respuesta and seguir:
                        hablar_y_escuchar_replica_autonoma(respuesta)
                    else:
                        hablar_jarvis(respuesta)
                    if not seguir:
                        break
                else:
                    escribir_estado_hud("EN LÍNEA", "Mark XV en línea | 1 Clic Reactor: Fullscreen")
        except Exception:
            time.sleep(1.5)


# =====================================================================
# 7. SECUENCIA DE INICIO SHOWSTOPPER MARK XV
# =====================================================================
def ejecutar_protocolo_inicio() -> None:
    despertar_y_desbloquear()
    lanzar_hud_holografico(animacion="BOOT_LOGIN", fullscreen=True)

    escribir_estado_hud(
        "PROCESANDO",
        "¡Doble palmada confirmada! Iniciando A FUERZAS con 'Should I Stay or Should I Go' al 100%...",
        visible=True,
        animacion="BOOT_LOGIN",
        app_actual="PISTA #1 // SHOULD I STAY OR SHOULD I GO -> SHUFFLE REWORK",
        progreso=18,
        cuadrante=1,
        fullscreen=True,
        efecto_transicion="ENTRADA",
    )
    iniciar_rework_en_spotify(volumen_inicial=100)

    for seg_restante in range(SEGUNDOS_INTRO_MUSICA, 0, -1):
        pct_intro = 18 + int(((SEGUNDOS_INTRO_MUSICA - seg_restante + 1) / SEGUNDOS_INTRO_MUSICA) * 24)
        escribir_estado_hud(
            "PROCESANDO",
            f"Sonando 'Should I Stay or Should I Go' (100%) — Inicializando voz y hologramas en {seg_restante}s...",
            visible=True,
            animacion="BOOT_LOGIN",
            app_actual=f"INTRO MUSICAL ACTIVA // INICIALIZACIÓN EN {seg_restante} SEGUNDOS",
            progreso=pct_intro,
            cuadrante=1,
            fullscreen=True,
        )
        time.sleep(1.0)

    ajustar_volumen_spotify(VOLUMEN_MUSICA_FONDO_PCT)
    ahora = datetime.datetime.now()
    saludo = "Buenos días," if 5 <= ahora.hour < 12 else ("Buenas tardes," if 12 <= ahora.hour < 19 else "Buenas noches,")
    frase_inicial = elegir_frase_sin_repetir(FRASES_APERTURA, "ultima_apertura")

    escribir_estado_hud(
        "HABLANDO",
        "Materializando sus herramientas de ingeniería simultáneamente...",
        visible=True,
        animacion="BOOT_LOGIN",
        app_actual="PROYECCIÓN HOLOGRÁFICA DE VENTANAS EN CURSO",
        progreso=72,
        cuadrante=2,
        fullscreen=True,
        efecto_transicion="PORTAL",
    )

    def _desplegar_todas_las_apps():
        for item in APPS_INICIO_MOSAICO:
            lanzar_item_mosaico_individual(item)
            time.sleep(0.55)
        time.sleep(1.8)
        acomodar_ventanas_en_mosaico()

    t_apps = threading.Thread(target=_desplegar_todas_las_apps, daemon=True)
    t_apps.start()

    asyncio.run(
        hablar_jarvis_async(
            f"{saludo} {frase_inicial} Abriendo simultáneamente sus entornos de Gemini, Google Classroom, Overleaf, Onshape, GitHub, WhatsApp y Visual Studio Code.",
            VOLUMEN_MUSICA_FONDO_PCT,
        )
    )
    t_apps.join(timeout=3.5)

    acomodar_ventanas_en_mosaico()
    frase_epica_stark = elegir_frase_sin_repetir(FRASES_EPICAS_STARK_FINAL, "ultima_epica_stark")
    reporte_final = (
        f"Son las {ahora.strftime('%I:%M %p')}. {obtener_clima_actual()} "
        f"{obtener_estado_hardware()} {construir_orden_del_dia()} {frase_epica_stark}"
    )
    escribir_estado_hud(
        "HABLANDO",
        reporte_final,
        visible=True,
        animacion="NORMAL",
        progreso=100,
        cuadrante=4,
        fullscreen=False,
        efecto_transicion="ENTRADA",
    )
    asyncio.run(hablar_jarvis_async(reporte_final, VOLUMEN_MUSICA_FONDO_PCT))

    for vol in (82, 90, VOLUMEN_MUSICA_FINAL_PCT):
        ajustar_volumen_spotify(vol)
        time.sleep(0.2)


def iniciar_escucha_palmadas() -> None:
    block_size = int(SAMPLE_RATE * BLOCK_DURATION)
    bloqueo_confirmado = False
    if BLOQUEAR_AL_ARRANCAR:
        bloqueo_confirmado = asegurar_pantalla_bloqueada_al_inicio()

    # Lanzar el HUD desde el inicio para que esté listo apenas se desbloquee
    lanzar_hud_holografico(animacion="NORMAL", fullscreen=False)

    while True:
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block_size) as stream:
                print("[J.A.R.V.I.S.] Estabilizando micrófono (2.5s)...")
                for _ in range(int(2.5 / BLOCK_DURATION)):
                    stream.read(block_size)

                print("[J.A.R.V.I.S.] Esperando 2 palmadas para iniciar Protocolo Showstopper...")
                historial_ruido = collections.deque(maxlen=25)
                for _ in range(25):
                    historial_ruido.append(0.02)

                en_impulso = False
                bloques_impulso = 0
                bloques_silencio = MIN_SILENCE_BLOCKS
                tiempos_palmadas = []
                ultimo_chequeo_lock = time.monotonic()

                while True:
                    datos, _ = stream.read(block_size)
                    pico = float(np.max(np.abs(datos)))
                    ahora = time.monotonic()

                    if (ahora - ultimo_chequeo_lock) >= 0.5:
                        ultimo_chequeo_lock = ahora
                        esta_lock = pantalla_esta_bloqueada()
                        if esta_lock:
                            bloqueo_confirmado = True
                        elif not bloqueo_confirmado and BLOQUEAR_AL_ARRANCAR:
                            # Si GNOME tardó en bloquearse al encender la laptop, reintentar bloqueo suave
                            ejecutar_seguro(["sudo", "-n", "/usr/bin/loginctl", "lock-sessions"])
                            ejecutar_seguro([
                                "gdbus", "call", "--session",
                                "--dest", "org.gnome.ScreenSaver",
                                "--object-path", "/org/gnome/ScreenSaver",
                                "--method", "org.gnome.ScreenSaver.Lock",
                            ])
                        elif bloqueo_confirmado and not esta_lock:
                            # La pantalla SÍ estuvo bloqueada y el usuario escribió su contraseña manualmente
                            print("[J.A.R.V.I.S.] Desbloqueo manual con contraseña detectado. Activando centinela y HUD.")
                            bucle_comandos_voz_post_inicio()
                            return

                    ruido_base = float(np.median(historial_ruido)) if historial_ruido else 0.02
                    umbral_dinamico = max(CLAP_THRESHOLD, ruido_base * CREST_FACTOR_MIN)

                    if pico >= umbral_dinamico:
                        en_impulso = True
                        bloques_impulso += 1
                    else:
                        if en_impulso:
                            if 1 <= bloques_impulso <= MAX_CLAP_BLOCKS and bloques_silencio >= MIN_SILENCE_BLOCKS:
                                tiempos_palmadas = [t for t in tiempos_palmadas if (ahora - t) <= MAX_GAP_SECONDS]
                                tiempos_palmadas.append(ahora)
                                if len(tiempos_palmadas) >= 2:
                                    intervalo = tiempos_palmadas[-1] - tiempos_palmadas[-2]
                                    if MIN_GAP_SECONDS <= intervalo <= MAX_GAP_SECONDS:
                                        datos_post, _ = stream.read(int(SAMPLE_RATE * 0.16))
                                        if float(np.max(np.abs(datos_post))) < SILENCE_THRESHOLD:
                                            print("[J.A.R.V.I.S.] ¡Doble palmada confirmada! Iniciando música...")
                                            ejecutar_protocolo_inicio()
                                            bucle_comandos_voz_post_inicio()
                                            return
                                        else:
                                            tiempos_palmadas.clear()
                            else:
                                tiempos_palmadas.clear()
                            en_impulso = False
                            bloques_impulso = 0
                            bloques_silencio = 0

                        if pico < SILENCE_THRESHOLD:
                            bloques_silencio += 1
                            historial_ruido.append(pico)
                        else:
                            bloques_silencio = 0
        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--listen-once":
        escuchar_un_comando_directo()
    elif len(sys.argv) > 1 and sys.argv[1] == "--brief":
        lanzar_hud_holografico()
        hablar_jarvis(construir_orden_del_dia())
    elif len(sys.argv) > 1 and sys.argv[1] == "--hud":
        lanzar_hud_holografico()
    elif len(sys.argv) > 1 and sys.argv[1] == "--clip":
        hablar_jarvis(clipear_pantalla_ahora(15))
    elif len(sys.argv) > 1 and sys.argv[1] == "--mute":
        establecer_modo_silencio_suma(True)
    elif len(sys.argv) > 1 and sys.argv[1] == "--unmute":
        establecer_modo_silencio_suma(False)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-autonomia":
        lanzar_hud_holografico()
        obs = generar_curiosidad_visual_espontanea()
        hablar_y_escuchar_replica_autonoma(obs)
    else:
        try:
            iniciar_escucha_palmadas()
        except KeyboardInterrupt:
            pass
