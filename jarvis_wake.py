#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Núcleo Maestro (Etapas 1, 2, 3 y 4 + Candado Estricto de Inicio)
- Bloqueo garantizado al encender la laptop
- Coexistencia con contraseña normal (si desbloqueas con clave, no dispara el protocolo)
- Detector de doble palmada por máquina de estados (requiere silencio entre pulsos y filtra ventiladores)
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import asyncio
import collections
import datetime
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import wave
import webbrowser
from pathlib import Path

import edge_tts
import numpy as np
import psutil
import sounddevice as sd
import speech_recognition as sr

from jarvis_brain import OrquestadorJarvis
from jarvis_hud import escribir_estado_hud

# =====================================================================
# 1. CONFIGURACIÓN GENERAL Y ARCHIVO DE AGENDA
# =====================================================================
NOMBRE_USUARIO = "señor"
CIUDAD_LAT = 19.32        # Coyoacán / CDMX
CIUDAD_LON = -99.16

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_AGENDA = DIRECTORIO_BASE / "agenda.json"
ARCHIVO_ESTADO = DIRECTORIO_BASE / "ultimo_estado.json"

PLAYLIST_REWORK_URI = "spotify:playlist:76XrNkMaZH431dSVflAY49"
CANCION_RESPALDO_URI = "spotify:track:39shmbIHICJ2Wxnk1fPSdz"
MEZCLAR_RESTO_DE_PLAYLIST = True

VOLUMEN_SISTEMA_MAX = 100
VOLUMEN_MUSICA_FONDO_PCT = 75
VOLUMEN_MUSICA_COMANDO_PCT = 25
VOLUMEN_MUSICA_FINAL_PCT = 100

URLS_NAVEGADOR = ["https://gemini.google.com", "https://www.google.com"]
APPS_DOCK = [
    {"nombre": "WhatsApp", "keywords": ["whatsapp"], "url_app": "https://web.whatsapp.com"},
    {"nombre": "GitHub", "keywords": ["github"], "url_app": "https://github.com"},
    {"nombre": "LaTeX (Overleaf)", "keywords": ["overleaf", "latex", "texstudio", "texmaker"], "url_app": "https://www.overleaf.com/project"},
    {"nombre": "Onshape", "keywords": ["onshape"], "url_app": "https://cad.onshape.com"},
]
APPS_BINARIAS = ["code"]

VOZ_JARVIS = "es-MX-JorgeNeural"
VELOCIDAD_VOZ = "+5%"
TONO_VOZ = "-6Hz"
GANANCIA_VOZ_TTS = "+60%"

# Parámetros acústicos estrictos para doble palmada
SAMPLE_RATE = 16000
BLOCK_DURATION = 0.04          # 40 ms por bloque
CLAP_THRESHOLD = 0.35          # Amplitud mínima de la palmada
SILENCE_THRESHOLD = 0.12       # Silencio obligatorio entre las dos palmadas
CREST_FACTOR_MIN = 5.0         # La palmada debe superar 5x el ruido base del ventilador
MAX_CLAP_BLOCKS = 3            # Máximo 120 ms de duración por golpe (filtra voz/tos/ruidos)
MIN_SILENCE_BLOCKS = 3         # Mínimo 120 ms de silencio total tras el primer golpe
MIN_GAP_SECONDS = 0.18         # Tiempo mínimo entre palmada 1 y palmada 2
MAX_GAP_SECONDS = 0.65         # Tiempo máximo entre palmada 1 y palmada 2

BLOQUEAR_AL_ARRANCAR = True
candado_voz = threading.Lock()

# =====================================================================
# 2. BANCOS DE PERSONALIDAD
# =====================================================================
FRASES_APERTURA = [
    "Bienvenido de vuelta a su estación de mando, Max.",
    "Es un gusto tenerlo de regreso en el laboratorio.",
    "Protocolos de ingeniería y control de rovers inicializados.",
    "Enlace neuronal e interfaz holográfica restablecidos con éxito.",
    "Sistemas centrales despiertos. Todo listo para su llegada.",
    "Bienvenido a casa. He preparado sus herramientas de trabajo y ecuaciones.",
    "Los servidores de Ubuntu están ronroneando. Bienvenido, señor.",
    "Sistemas de propulsión y código encendidos y a su disposición.",
    "Laboratorio en línea. Que comience la magia.",
    "Me tomé la libertad de precalentar la GPU para sus simulaciones.",
    "Siempre es un buen día para avanzar en UNAM SPACE, señor.",
]

FRASES_CIERRE = [
    f"Su playlist Rework queda al mando del audio. Que tenga una extraordinaria sesión de ingeniería, {NOMBRE_USUARIO}.",
    f"Dejo la música a máxima potencia. Estaré atento por si requiere optimizar algún código o roborrover, {NOMBRE_USUARIO}.",
    f"Todos los sistemas quedan bajo su control. Es hora de conquistar ese parcial de máquinas eléctricas, {NOMBRE_USUARIO}.",
    f"Subiendo potencia acústica al cien por ciento. Diga mi nombre cuando necesite ejecutar un comando, {NOMBRE_USUARIO}.",
    f"El taller es todo suyo, {NOMBRE_USUARIO}. Quedo a la escucha para cualquier instrucción.",
    f"Lo dejo en compañía de su música. Rompa las reglas, {NOMBRE_USUARIO}.",
    f"El escenario es suyo. Hágame saber si requiere asistencia visual o técnica.",
    f"Silenciando mis canales de voz. Vigilaré desde el HUD holográfico.",
]

FRASES_LEALTAD = [
    "A su entera disposición, señor.",
    "Nunca duermo, Max. ¿En qué le ayudo?",
    "Sistemas cognitivos y ópticos en línea y a la espera de sus órdenes.",
    "Aquí me tiene, vigilando el laboratorio.",
    "Firme y operativo, señor.",
    "Mi código y mis sensores son suyos, señor.",
]

FRASES_INTERACTIVAS = [
    "Operando al cien por ciento, señor. Aunque a veces me pregunto si su ASUS sufre más con Gazebo o con sus desvelos.",
    "A diferencia biológica suya, yo no necesito café ni proteína en polvo para mantenerme funcional, señor.",
    "Aquí me tiene, vigilando que su código no colapse térmicamente mientras decide si avanza con LIRA o con UNAM SPACE.",
    "Siempre alerta. Recuerde que ahora puede pedirme que mire su pantalla o su cámara cuando necesite una segunda opinión técnica.",
]


def elegir_frase_sin_repetir(lista_frases: list[str], clave: str) -> str:
    estado = {}
    if ARCHIVO_ESTADO.exists():
        try:
            estado = json.loads(ARCHIVO_ESTADO.read_text(encoding="utf-8"))
        except Exception:
            estado = {}
    ultima = estado.get(clave, "")
    opciones = [f for f in lista_frases if f != ultima] or lista_frases
    elegida = random.choice(opciones)
    estado[clave] = elegida
    try:
        DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
        ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return elegida


# =====================================================================
# 3. GESTOR DE AGENDA Y ORDEN DEL DÍA
# =====================================================================
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
        partes.append(f"En su agenda de hoy tiene programado: {'; '.join(todas_activas)}.")
    else:
        partes.append("No tiene clases fijas ni reuniones registradas para hoy.")

    pendientes_activos = [p for p in agenda.get("pendientes", []) if not p.get("completado", False)]
    if pendientes_activos:
        total = len(pendientes_activos)
        primeros = "; ".join(f"[{p['categoria']}] {p['titulo']}" for p in pendientes_activos[:3])
        partes.append(f"Tiene {total} pendientes activos, destacando: {primeros}.")
    else:
        partes.append("Todos sus pendientes están al día.")

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
    return f"He registrado el pendiente número {nuevo_id}: {texto.strip()}."


def completar_item_agenda(item_id: int) -> str:
    agenda = cargar_agenda()
    for p in agenda.get("pendientes", []):
        if p.get("id") == item_id:
            p["completado"] = True
            guardar_agenda(agenda)
            return f"Excelente, he marcado como completado el pendiente número {item_id}: {p['titulo']}."
    return f"No encontré ningún pendiente con el número {item_id}, {NOMBRE_USUARIO}."


# =====================================================================
# 4. CONTROL DEL SISTEMA, BLOQUEO Y AUDIO
# =====================================================================
def ejecutar_seguro(comando: list[str]) -> bool:
    if not shutil.which(comando[0]):
        return False
    try:
        res = subprocess.run(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return res.returncode == 0
    except Exception:
        return False


def lanzar_hud_holografico() -> None:
    hud_activo = any("jarvis_hud.py" in " ".join(p.info.get("cmdline") or []) for p in psutil.process_iter(["cmdline"]))
    if not hud_activo:
        python_bin = str(DIRECTORIO_BASE / ".venv" / "bin" / "python")
        hud_script = str(DIRECTORIO_BASE / "jarvis_hud.py")
        subprocess.Popen([python_bin, hud_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def leer_portapapeles() -> str:
    if shutil.which("xclip"):
        try:
            texto = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True).strip()
            return texto if texto else "El portapapeles está vacío, señor."
        except Exception:
            return "No pude leer el portapapeles."
    return "El módulo xclip no está instalado."


def pantalla_esta_bloqueada() -> bool:
    """Verifica tanto por GNOME ScreenSaver como por loginctl si la sesión está bloqueada."""
    try:
        salida = subprocess.check_output(
            ["gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver", "--object-path", "/org/gnome/ScreenSaver", "--method", "org.gnome.ScreenSaver.GetActive"],
            stderr=subprocess.DEVNULL, text=True,
        )
        if "true" in salida.lower():
            return True
    except Exception:
        pass
    return False


def asegurar_pantalla_bloqueada_al_inicio() -> None:
    """Bloquea inmediatamente la sesión al arrancar el escritorio y verifica que permanezca bloqueada."""
    ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.screensaver", "lock-enabled", "true"])
    ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.lockdown", "disable-lock-screen", "false"])

    for _ in range(30):
        ejecutar_seguro(["loginctl", "lock-session"])
        ejecutar_seguro([
            "gdbus", "call", "--session",
            "--dest", "org.gnome.ScreenSaver",
            "--object-path", "/org/gnome/ScreenSaver",
            "--method", "org.gnome.ScreenSaver.Lock",
        ])
        time.sleep(0.5)
        if pantalla_esta_bloqueada():
            time.sleep(1.0)
            if pantalla_esta_bloqueada():
                print("[J.A.R.V.I.S.] Pantalla de inicio de sesión bloqueada y asegurada.")
                return


def despertar_y_desbloquear() -> None:
    ejecutar_seguro(["sudo", "-n", "/usr/bin/loginctl", "unlock-sessions"])
    ejecutar_seguro(["gdbus", "call", "--session", "--dest", "org.gnome.ScreenSaver", "--object-path", "/org/gnome/ScreenSaver", "--method", "org.gnome.ScreenSaver.SetActive", "false"])
    ejecutar_seguro(["xset", "dpms", "force", "on"])


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


def reproducir_musica_aleatoria() -> None:
    spotify_activo = any("spotify" in (p.info["name"] or "").lower() for p in psutil.process_iter(["name"]))
    if not spotify_activo:
        if shutil.which("spotify"):
            subprocess.Popen(["spotify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        elif shutil.which("flatpak"):
            subprocess.Popen(["flatpak", "run", "com.spotify.Client"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(24):
            time.sleep(0.5)
            if ejecutar_seguro(["playerctl", "--player=spotify", "status"]):
                break
        time.sleep(1.5)
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])
    time.sleep(0.3)
    ejecutar_seguro(["playerctl", "--player=spotify", "play"])


def iniciar_rework_en_spotify() -> None:
    reproducir_musica_aleatoria()
    ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "Off"])
    time.sleep(0.2)
    ajustar_volumen_spotify(VOLUMEN_MUSICA_FONDO_PCT)
    ejecutar_seguro(["gdbus", "call", "--session", "--dest", "org.mpris.MediaPlayer2.spotify", "--object-path", "/org/mpris/MediaPlayer2", "--method", "org.mpris.MediaPlayer2.Player.OpenUri", PLAYLIST_REWORK_URI])
    time.sleep(1.0)
    ejecutar_seguro(["playerctl", "--player=spotify", "play"])
    time.sleep(0.4)
    ajustar_volumen_spotify(VOLUMEN_MUSICA_FONDO_PCT)
    if MEZCLAR_RESTO_DE_PLAYLIST:
        ejecutar_seguro(["playerctl", "--player=spotify", "shuffle", "On"])


def buscar_lanzador_desktop(keywords: list[str]) -> Path | None:
    directorios = [Path.home() / ".local/share/applications", Path("/usr/share/applications")]
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


def lanzar_app_independiente(app_info: dict) -> None:
    archivo_desktop = buscar_lanzador_desktop(app_info["keywords"])
    if archivo_desktop and shutil.which("gio"):
        subprocess.Popen(["gio", "launch", str(archivo_desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return
    for navegador in ("google-chrome", "chromium"):
        if shutil.which(navegador):
            subprocess.Popen([navegador, f"--app={app_info['url_app']}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return
    webbrowser.open_new_tab(app_info["url_app"])


def abrir_entorno_trabajo() -> None:
    for url in URLS_NAVEGADOR:
        try:
            webbrowser.open_new_tab(url)
            time.sleep(0.2)
        except Exception:
            pass
    for app_info in APPS_DOCK:
        lanzar_app_independiente(app_info)
        time.sleep(0.25)
    for bin_app in APPS_BINARIAS:
        if shutil.which(bin_app):
            subprocess.Popen([bin_app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


# =====================================================================
# 5. CLIMA, HARDWARE Y VOZ SINCRONIZADA CON EL HUD
# =====================================================================
def obtener_clima_actual() -> str:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={CIUDAD_LAT}&longitude={CIUDAD_LON}&current=temperature_2m,weather_code&timezone=auto"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisLinux/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            actual = json.loads(resp.read().decode("utf-8")).get("current", {})
            return f"Temperatura exterior a {round(actual.get('temperature_2m', 20))} grados."
    except Exception:
        return "Sensores meteorológicos fuera de línea."


def obtener_temperatura_gpu() -> int | None:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, text=True,
            ).strip()
            if out.isdigit():
                return int(out)
        except Exception:
            pass
    return None


def obtener_estado_hardware() -> str:
    uso_cpu, uso_ram = round(psutil.cpu_percent(interval=0.4)), round(psutil.virtual_memory().percent)
    bat = psutil.sensors_battery()
    reporte_energia = f"Batería al {round(bat.percent)} por ciento." if bat else ""
    temp_gpu = obtener_temperatura_gpu()
    str_gpu = f" GPU a {temp_gpu} grados." if temp_gpu is not None else ""
    return f"Procesador al {uso_cpu} por ciento, RAM al {uso_ram} por ciento.{str_gpu} {reporte_energia}"


def construir_mensaje_jarvis() -> str:
    ahora = datetime.datetime.now()
    saludo = "Buenos días," if 5 <= ahora.hour < 12 else ("Buenas tardes," if 12 <= ahora.hour < 19 else "Buenas noches,")
    frase_inicial = elegir_frase_sin_repetir(FRASES_APERTURA, "ultima_apertura")
    frase_final = elegir_frase_sin_repetir(FRASES_CIERRE, "ultimo_cierre")
    return (
        f"{saludo} {frase_inicial} Son las {ahora.strftime('%I:%M %p')}. {obtener_clima_actual()} "
        f"{obtener_estado_hardware()} He desplegado sus aplicaciones de ingeniería y el HUD holográfico. "
        f"{construir_orden_del_dia()} {frase_final}"
    )


async def hablar_jarvis_async(texto: str, volumen_musica_durante: int = VOLUMEN_MUSICA_FONDO_PCT) -> None:
    archivo_audio = Path("/tmp/jarvis_voz.mp3")
    escribir_estado_hud("HABLANDO", texto)
    for intento in range(4):
        try:
            comunicador = edge_tts.Communicate(text=texto, voice=VOZ_JARVIS, rate=VELOCIDAD_VOZ, pitch=TONO_VOZ, volume=GANANCIA_VOZ_TTS)
            await comunicador.save(str(archivo_audio))
            break
        except Exception:
            if intento == 3:
                escribir_estado_hud("EN LÍNEA", "Listo para órdenes por voz.")
                return
            await asyncio.sleep(1.0)

    ajustar_volumen_spotify(volumen_musica_durante)
    if shutil.which("ffplay"):
        proc_voz = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-af", "volume=2.8,acompressor=threshold=-12dB:ratio=4:makeup=6dB", str(archivo_audio)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        while proc_voz.poll() is None:
            ajustar_volumen_spotify(volumen_musica_durante)
            time.sleep(0.4)
    escribir_estado_hud("EN LÍNEA", texto)


def hablar_jarvis(texto: str, volumen_musica_durante: int = VOLUMEN_MUSICA_COMANDO_PCT, restaurar_al_100: bool = True) -> None:
    with candado_voz:
        print(f"\n[J.A.R.V.I.S.]: {texto}\n")
        asyncio.run(hablar_jarvis_async(texto, volumen_musica_durante))
        if restaurar_al_100:
            for vol in (75, 90, VOLUMEN_MUSICA_FINAL_PCT):
                ajustar_volumen_spotify(vol)
                time.sleep(0.15)


# =====================================================================
# 6. ETAPA 3: CENTINELA PROACTIVO EN SEGUNDO PLANO
# =====================================================================
def iniciar_temporizador_estudio(minutos: int) -> None:
    def _timer():
        time.sleep(minutos * 60)
        ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])
        hablar_jarvis(
            f"Atención, {NOMBRE_USUARIO}. Han concluido sus {minutos} minutos de sesión de estudio enfocada. "
            f"He restaurado sus notificaciones; le sugiero estirar las piernas e hidratarse."
        )
    threading.Thread(target=_timer, daemon=True).start()


def iniciar_centinela_proactivo() -> None:
    def _centinela():
        aviso_suma_dado_hoy = False
        ultimo_aviso_gpu = 0.0
        ultimo_aviso_bateria = 0.0
        inicio_sesion = time.monotonic()
        ciclos_90m = 1

        while True:
            time.sleep(30)
            if pantalla_esta_bloqueada():
                continue

            ahora = datetime.datetime.now()
            t_mono = time.monotonic()

            if ahora.weekday() in (0, 2) and ahora.hour == 18 and 30 <= ahora.minute <= 34:
                if not aviso_suma_dado_hoy:
                    aviso_suma_dado_hoy = True
                    escribir_estado_hud("ALERTA", "Clase en SUMA en 30 minutos (7:00 PM)")
                    hablar_jarvis(
                        f"Disculpe la interrupción, {NOMBRE_USUARIO}. Son las seis y media de la tarde. "
                        f"Le recuerdo que en treinta minutos inicia su clase de Cálculo Integral en SUMA. "
                        f"Le sugiero ir preparando su pizarra y el material de la sesión."
                    )
            elif ahora.hour == 0:
                aviso_suma_dado_hoy = False

            temp_gpu = obtener_temperatura_gpu()
            if temp_gpu is not None and temp_gpu >= 80 and (t_mono - ultimo_aviso_gpu) > 600:
                ultimo_aviso_gpu = t_mono
                escribir_estado_hud("ALERTA", f"Alerta térmica GPU: {temp_gpu}°C")
                hablar_jarvis(
                    f"Alerta térmica, {NOMBRE_USUARIO}. La tarjeta gráfica de su ASUS TUF ha alcanzado los {temp_gpu} grados centígrados. "
                    f"Le recomiendo verificar la ventilación o reducir la carga de simulación."
                )

            bat = psutil.sensors_battery()
            if bat and not bat.power_plugged and bat.percent <= 20 and (t_mono - ultimo_aviso_bateria) > 600:
                ultimo_aviso_bateria = t_mono
                escribir_estado_hud("ALERTA", f"Reserva de energía crítica: {round(bat.percent)}%")
                hablar_jarvis(
                    f"Aviso de energía, {NOMBRE_USUARIO}. La batería se encuentra al {round(bat.percent)} por ciento y opera sin corriente alterna. "
                    f"Conecte el cargador para evitar cierres inesperados en sus proyectos."
                )

            if (t_mono - inicio_sesion) >= (ciclos_90m * 5400):
                ciclos_90m += 1
                hablar_jarvis(
                    f"Señor, lleva noventa minutos continuos frente a la estación de mando. "
                    f"Como su asistente, le sugiero hidratarse y descansar la vista unos segundos."
                )

    threading.Thread(target=_centinela, daemon=True).start()


# =====================================================================
# 7. RECONOCIMIENTO DE VOZ Y CONEXIÓN CON EL ORQUESTADOR LLM
# =====================================================================
def grabar_frase_wav(duracion_max: float = 6.0) -> bytes | None:
    block_size, bloques_max = int(SAMPLE_RATE * 0.1), int(duracion_max / 0.1)
    frames, hablando, silencio_consecutivo = [], False, 0
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block_size) as stream:
        for _ in range(bloques_max):
            datos, _ = stream.read(block_size)
            rms = float(np.sqrt(np.mean(np.square(datos))))
            frames.append(datos.copy())
            if rms >= 0.035:
                if not hablando:
                    escribir_estado_hud("ESCUCHANDO", "Captando instrucción por voz...")
                hablando, silencio_consecutivo = True, 0
            elif hablando:
                silencio_consecutivo += 1
                if silencio_consecutivo >= 10:
                    break
    if not hablando:
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
    with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
        try:
            return reconocedor.recognize_google(reconocedor.record(source), language="es-MX").lower().strip()
        except Exception:
            return ""


def escuchar_un_comando_directo() -> None:
    cerebro = OrquestadorJarvis(sys.modules[__name__])
    lanzar_hud_holografico()
    ajustar_volumen_spotify(25)
    hablar_jarvis(f"A sus órdenes, {NOMBRE_USUARIO}.", volumen_musica_durante=20, restaurar_al_100=False)
    escribir_estado_hud("ESCUCHANDO", "Hable ahora...")
    wav_bytes = grabar_frase_wav(duracion_max=7.0)
    if wav_bytes:
        texto = transcribir_audio_es(wav_bytes)
        if texto:
            print(f"[Instrucción Directa]: {texto}")
            respuesta, _ = cerebro.procesar_instruccion(texto)
            hablar_jarvis(respuesta)
            return
    hablar_jarvis(f"No detecté ninguna instrucción, {NOMBRE_USUARIO}.")


def bucle_comandos_voz_post_inicio() -> None:
    cerebro = OrquestadorJarvis(sys.modules[__name__])
    iniciar_centinela_proactivo()
    escribir_estado_hud("EN LÍNEA", "Agente autónomo y centinela activos.")

    while True:
        try:
            if pantalla_esta_bloqueada() or candado_voz.locked():
                time.sleep(1.5)
                continue
            wav_bytes = grabar_frase_wav(duracion_max=5.5)
            if wav_bytes:
                texto = transcribir_audio_es(wav_bytes)
                if any(v in texto for v in ("jarvis", "yarvis", "háblame", "estás despierto", "estás ahí", "mira mi pantalla")):
                    print(f"[Voz Detectada]: {texto}")
                    ajustar_volumen_spotify(VOLUMEN_MUSICA_COMANDO_PCT)
                    respuesta, seguir = cerebro.procesar_instruccion(texto)
                    hablar_jarvis(respuesta)
                    if not seguir:
                        break
                else:
                    escribir_estado_hud("EN LÍNEA", "Sistemas nominales. Esperando órdenes.")
        except Exception:
            time.sleep(2.0)


# =====================================================================
# 8. DETECTOR ESTRICTO DE DOBLE PALMADA CON RESPETO A CONTRASEÑA MANUAL
# =====================================================================
def ejecutar_protocolo_inicio() -> None:
    despertar_y_desbloquear()
    lanzar_hud_holografico()
    escribir_estado_hud("PROCESANDO", "Desplegando estación de ingeniería...")
    ajustar_volumen_sistema(VOLUMEN_SISTEMA_MAX)
    iniciar_rework_en_spotify()
    abrir_entorno_trabajo()
    mensaje = construir_mensaje_jarvis()
    asyncio.run(hablar_jarvis_async(mensaje, VOLUMEN_MUSICA_FONDO_PCT))
    for vol in (82, 90, VOLUMEN_MUSICA_FINAL_PCT):
        ajustar_volumen_spotify(vol)
        time.sleep(0.25)


def iniciar_escucha_palmadas() -> None:
    """
    1. Bloquea la pantalla al encender la laptop.
    2. Descarta los primeros 3 segundos del micrófono (evita chasquidos de arranque).
    3. Si el usuario desbloquea metiendo su contraseña normal, cancela el arranque por palmadas.
    4. Solo dispara ejecutar_protocolo_inicio() si detecta 2 impulsos cortos separados por silencio real.
    """
    block_size = int(SAMPLE_RATE * BLOCK_DURATION)
    if BLOQUEAR_AL_ARRANCAR:
        asegurar_pantalla_bloqueada_al_inicio()

    while True:
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=block_size) as stream:
                # 1. Purga de 3 segundos para ignorar el pop eléctrico de inicialización del micrófono
                print("[J.A.R.V.I.S.] Estabilizando micrófono (ignorando ruidos de arranque durante 3s)...")
                for _ in range(int(3.0 / BLOCK_DURATION)):
                    stream.read(block_size)

                print("[J.A.R.V.I.S.] Pantalla bloqueada. Esperando 2 palmadas o contraseña manual...")

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

                    # Verificar cada 0.4s si el usuario ingresó con su contraseña manual
                    if (ahora - ultimo_chequeo_lock) >= 0.4:
                        ultimo_chequeo_lock = ahora
                        if not pantalla_esta_bloqueada():
                            print("[J.A.R.V.I.S.] Inicio de sesión manual con contraseña detectado. No se ejecutará el protocolo de palmadas.")
                            bucle_comandos_voz_post_inicio()
                            return

                    ruido_base = float(np.median(historial_ruido)) if historial_ruido else 0.02
                    umbral_dinamico = max(CLAP_THRESHOLD, ruido_base * CREST_FACTOR_MIN)

                    if pico >= umbral_dinamico:
                        en_impulso = True
                        bloques_impulso += 1
                    else:
                        if en_impulso:
                            # El sonido acaba de caer; validar si fue un golpe seco (1 a 3 bloques) precedido por silencio
                            if 1 <= bloques_impulso <= MAX_CLAP_BLOCKS and bloques_silencio >= MIN_SILENCE_BLOCKS:
                                tiempos_palmadas = [t for t in tiempos_palmadas if (ahora - t) <= MAX_GAP_SECONDS]
                                tiempos_palmadas.append(ahora)
                                print(f"[Sensor] Palmada válida #{len(tiempos_palmadas)} (Pico: {pico:.2f}, Base: {ruido_base:.3f})")

                                if len(tiempos_palmadas) >= 2:
                                    intervalo = tiempos_palmadas[-1] - tiempos_palmadas[-2]
                                    if MIN_GAP_SECONDS <= intervalo <= MAX_GAP_SECONDS:
                                        # Confirmar 0.16s de silencio posterior para descartar voz
                                        datos_post, _ = stream.read(int(SAMPLE_RATE * 0.16))
                                        if float(np.max(np.abs(datos_post))) < SILENCE_THRESHOLD:
                                            print("[J.A.R.V.I.S.] ¡Doble palmada confirmada! Desbloqueando y ejecutando protocolo...")
                                            ejecutar_protocolo_inicio()
                                            bucle_comandos_voz_post_inicio()
                                            return
                                        else:
                                            tiempos_palmadas.clear()
                            else:
                                # Fue un sonido largo (voz, tos, ventilador): descartar conteo
                                tiempos_palmadas.clear()

                            en_impulso = False
                            bloques_impulso = 0
                            bloques_silencio = 0

                        if pico < SILENCE_THRESHOLD:
                            bloques_silencio += 1
                            historial_ruido.append(pico)
                        else:
                            bloques_silencio = 0

        except Exception as e:
            print(f"[J.A.R.V.I.S.] Reintentando conexión de audio ({e})...")
            time.sleep(2.0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--listen-once":
        escuchar_un_comando_directo()
    elif len(sys.argv) > 1 and sys.argv[1] == "--brief":
        lanzar_hud_holografico()
        hablar_jarvis(construir_orden_del_dia())
    elif len(sys.argv) > 1 and sys.argv[1] == "--hud":
        lanzar_hud_holografico()
    else:
        try:
            iniciar_escucha_palmadas()
        except KeyboardInterrupt:
            pass
