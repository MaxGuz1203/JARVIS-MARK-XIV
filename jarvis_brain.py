#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Etapas 1 y 2:
- Orquestador Cognitivo LLM con Function Calling y Auto-Detección de Modelo
- Ojos de J.A.R.V.I.S. (Visión Multimodal de Pantalla y Cámara Web bajo demanda)
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import datetime
import os
import random
import shutil
import subprocess
from pathlib import Path

import cv2
from PIL import Image, ImageGrab

from jarvis_hud import escribir_estado_hud

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_ENV = DIRECTORIO_BASE / ".env"
MODELO_ACTIVO_CACHE = None

SYSTEM_PROMPT_JARVIS = """
Eres J.A.R.V.I.S. (Just A Rather Very Intelligent System), el asistente personal de inteligencia artificial e ingeniería de Luis Maximiliano Guzmán Ortiz (a quien te diriges como "señor" o "Max").
Contexto de tu creador:
- Estudiante de 7° semestre de Ingeniería Eléctrica Electrónica en la FI UNAM.
- Co-Fundador y CTEO de SUMA (imparte Cálculo Integral lunes y miércoles de 7:00 PM a 9:00 PM).
- Capitán y líder de Electrónica de Potencia en UNAM SPACE (diseño de rovers y PCBs).
- Investigador en LIRA (ROS 2 Navigation Costmaps y etiquetado en Labelme).
- Opera una laptop ASUS TUF Gaming F16 con Ubuntu Linux 24.04.

Reglas de estilo y formato:
1. Habla siempre en español de México formal, sofisticado, leal y con un sutil toque de ingenio e ironía británica estilo J.A.R.V.I.S.
2. Tus respuestas serán leídas en voz alta por un motor TTS: sé conciso (máximo 2 a 4 oraciones claras), NO uses bloques largos de Markdown ni asteriscos, y escribe siglas o números de forma natural para ser hablados.
3. Siempre que el usuario pida una acción en su laptop (música, agenda, abrir programas, mirar su pantalla, mirar la cámara, ver telemetría o controlar el HUD), EJECUTA la herramienta correspondiente mediante Function Calling antes de responder.
"""


def cargar_api_key() -> str:
    """Lee GEMINI_API_KEY desde variables de entorno o desde ~/jarvis/.env."""
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
    """Detecta y memoriza el modelo Gemini Flash habilitado en la cuenta (evitando 2.5/1.5 retirados)."""
    global MODELO_ACTIVO_CACHE

    if MODELO_ACTIVO_CACHE:
        if config is not None:
            return client.models.generate_content(model=MODELO_ACTIVO_CACHE, contents=contents, config=config)
        return client.models.generate_content(model=MODELO_ACTIVO_CACHE, contents=contents)

    candidatos = [
        "gemini-3-flash",
        "gemini-3.0-flash",
        "gemini-3-flash-preview",
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
            if config is not None:
                res = client.models.generate_content(model=mod, contents=contents, config=config)
            else:
                res = client.models.generate_content(model=mod, contents=contents)
            MODELO_ACTIVO_CACHE = mod
            print(f"[Cerebro J.A.R.V.I.S.] Conectado exitosamente al modelo: {mod}")
            return res
        except Exception as e:
            ultimo_error = e
            continue

    raise ultimo_error


# =====================================================================
# ETAPA 2: OJOS DE J.A.R.V.I.S. (CAPTURA DE PANTALLA Y CÁMARA WEB)
# =====================================================================
def capturar_pantalla_actual() -> Path | None:
    """Toma una captura silenciosa del escritorio en X11 o Wayland."""
    ruta_img = Path("/tmp/jarvis_vision_screen.png")
    if ruta_img.exists():
        ruta_img.unlink()

    if shutil.which("gnome-screenshot"):
        subprocess.run(["gnome-screenshot", "-f", str(ruta_img)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if ruta_img.exists():
            return ruta_img

    if shutil.which("scrot"):
        subprocess.run(["scrot", str(ruta_img)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if ruta_img.exists():
            return ruta_img

    try:
        img = ImageGrab.grab()
        img.save(str(ruta_img))
        return ruta_img
    except Exception:
        return None


def capturar_foto_webcam() -> Path | None:
    """Abre la cámara web (/dev/video0), calibra la exposición y captura un fotograma."""
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
    """Envía la imagen capturada (pantalla o webcam) al modelo multimodal de Gemini."""
    api_key = cargar_api_key()
    if not api_key:
        return "Señor, mis sensores ópticos capturaron la imagen, pero necesito que configure su clave de Gemini en el archivo punto env para procesarla."

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        imagen_pil = Image.open(ruta_imagen)
        prompt = (
            f"Actúa como J.A.R.V.I.S. Analiza esta imagen y responde de forma concisa y hablada "
            f"(sin formato markdown ni asteriscos) a la solicitud de Max: '{pregunta_usuario}'. "
            f"Si ves código con errores, terminales de ROS 2, diagramas eléctricos o CAD en Onshape, sé técnicamente preciso."
        )
        respuesta = generar_con_modelo_activo(client, contents=[imagen_pil, prompt])
        return respuesta.text.replace("*", "").strip()
    except Exception as e:
        return f"Ocurrió una anomalía al procesar la señal de video, señor: {e}"


# =====================================================================
# ETAPA 1: ORQUESTADOR COGNITIVO CON FUNCTION CALLING
# =====================================================================
class OrquestadorJarvis:
    """Conecta las funciones nativas de tu laptop como herramientas invocables por el LLM."""

    def __init__(self, modulo_sistema) -> None:
        self.sys = modulo_sistema

    def procesar_instruccion(self, texto_usuario: str) -> tuple[str, bool]:
        cmd_low = texto_usuario.lower().strip()

        if any(k in cmd_low for k in ("estás despierto", "estas despierto")):
            frase = f"Para usted, siempre, señor. {random.choice(self.sys.FRASES_LEALTAD)}"
            return frase, True

        if any(k in cmd_low for k in ("descansa", "apágate", "apagate", "desconéctate")):
            return f"Entendido, {self.sys.NOMBRE_USUARIO}. Desactivando escucha activa. Hasta pronto.", False

        api_key = cargar_api_key()
        if not api_key:
            return self._respaldo_local(cmd_low), True

        escribir_estado_hud("PROCESANDO", f"Analizando: {texto_usuario}")

        def tool_controlar_spotify(accion: str, porcentaje_volumen: int = -1) -> str:
            """Controla Spotify. accion puede ser: 'play', 'pause', 'next', 'previous', 'rework', 'volumen'."""
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
            if porcentaje_volumen >= 0:
                self.sys.ajustar_volumen_sistema(porcentaje_volumen)
                self.sys.ajustar_volumen_spotify(porcentaje_volumen)
            return f"Acción de Spotify '{accion}' ejecutada correctamente."

        def tool_consultar_agenda_y_orden_del_dia() -> str:
            """Devuelve la orden del día completa, clases de SUMA, tareas de LIRA, UNAM SPACE y materias."""
            return self.sys.construir_orden_del_dia()

        def tool_agregar_pendiente(titulo_tarea: str, tipo: str = "pendiente") -> str:
            """Agrega una nueva tarea o reunión a la agenda. tipo puede ser 'pendiente' o 'reunion'."""
            return self.sys.agregar_item_agenda(tipo, titulo_tarea)

        def tool_completar_pendiente(id_numero: int) -> str:
            """Marca como completado un pendiente de la agenda usando su número de ID."""
            return self.sys.completar_item_agenda(id_numero)

        def tool_abrir_aplicacion(nombre_aplicacion: str) -> str:
            """Abre una aplicación en Ubuntu: 'terminal', 'calculadora', 'archivos', 'vscode', 'labelme', 'onshape', 'latex', 'github', 'whatsapp', 'rviz', 'gazebo'."""
            app = nombre_aplicacion.lower()
            if "terminal" in app:
                subprocess.Popen(["gnome-terminal"], start_new_session=True)
            elif "calcul" in app:
                subprocess.Popen(["gnome-calculator"], start_new_session=True)
            elif "archivo" in app or "carpeta" in app:
                subprocess.Popen(["nautilus", str(Path.home())], start_new_session=True)
            elif "code" in app or "visual" in app:
                subprocess.Popen(["code"], start_new_session=True)
            elif "labelme" in app:
                subprocess.Popen(["bash", "-ic", "labelme"], start_new_session=True)
            elif "rviz" in app:
                subprocess.Popen(["bash", "-ic", "rviz2"], start_new_session=True)
            elif "gazebo" in app:
                subprocess.Popen(["bash", "-ic", "gz sim"], start_new_session=True)
            elif "onshape" in app:
                self.sys.lanzar_app_independiente(self.sys.APPS_DOCK[3])
            elif "latex" in app or "overleaf" in app:
                self.sys.lanzar_app_independiente(self.sys.APPS_DOCK[2])
            elif "github" in app:
                self.sys.lanzar_app_independiente(self.sys.APPS_DOCK[1])
            elif "whatsapp" in app:
                self.sys.lanzar_app_independiente(self.sys.APPS_DOCK[0])
            else:
                return f"Aplicación {nombre_aplicacion} no reconocida."
            return f"Aplicación {nombre_aplicacion} iniciada."

        def tool_consultar_telemetria_y_clima() -> str:
            """Obtiene uso de CPU, RAM, temperatura de GPU NVIDIA, porcentaje de batería, hora actual y clima en CDMX."""
            ahora = datetime.datetime.now().strftime("%I:%M %p")
            return f"Hora: {ahora}. {self.sys.obtener_clima_actual()} {self.sys.obtener_estado_hardware()}"

        def tool_mirar_pantalla(pregunta_sobre_pantalla: str) -> str:
            """Toma una captura de la pantalla actual de la laptop y la analiza con visión artificial."""
            escribir_estado_hud("PROCESANDO", "Capturando y analizando pantalla...")
            ruta = capturar_pantalla_actual()
            if not ruta:
                return "No fue posible capturar la pantalla actual."
            return analizar_imagen_con_gemini(ruta, pregunta_sobre_pantalla)

        def tool_mirar_camara_web(pregunta_sobre_camara: str) -> str:
            """Toma una foto con la cámara web de la laptop para analizar objetos, circuitos o apuntes."""
            escribir_estado_hud("PROCESANDO", "Activando cámara óptica...")
            ruta = capturar_foto_webcam()
            if not ruta:
                return "No pude acceder a la cámara web en /dev/video0."
            return analizar_imagen_con_gemini(ruta, pregunta_sobre_camara)

        def tool_leer_portapapeles() -> str:
            """Lee el texto que el usuario tenga copiado actualmente en el portapapeles de Ubuntu."""
            return self.sys.leer_portapapeles()

        def tool_iniciar_sesion_estudio(minutos: int = 45) -> str:
            """Inicia un temporizador de sesión de estudio enfocada, silencia notificaciones y atenúa la música."""
            self.sys.iniciar_temporizador_estudio(minutos)
            self.sys.ejecutar_seguro(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
            self.sys.ajustar_volumen_spotify(25)
            return f"Sesión de estudio de {minutos} minutos iniciada."

        def tool_controlar_hud_holografico(mostrar: bool) -> str:
            """Muestra u oculta el panel HUD holográfico en la pantalla."""
            escribir_estado_hud("EN LÍNEA", "Visibilidad del HUD actualizada", visible=mostrar)
            return "HUD mostrado." if mostrar else "HUD ocultado."

        def tool_bloquear_estacion() -> str:
            """Bloquea inmediatamente la pantalla de Ubuntu por seguridad."""
            self.sys.ejecutar_seguro(["loginctl", "lock-session"])
            return "Estación bloqueada."

        herramientas = [
            tool_controlar_spotify,
            tool_consultar_agenda_y_orden_del_dia,
            tool_agregar_pendiente,
            tool_completar_pendiente,
            tool_abrir_aplicacion,
            tool_consultar_telemetria_y_clima,
            tool_mirar_pantalla,
            tool_mirar_camara_web,
            tool_leer_portapapeles,
            tool_iniciar_sesion_estudio,
            tool_controlar_hud_holografico,
            tool_bloquear_estacion,
        ]

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_JARVIS,
                tools=herramientas,
                temperature=0.65,
            )

            respuesta = generar_con_modelo_activo(
                client,
                contents=texto_usuario,
                config=config,
            )
            texto_final = (respuesta.text or "").replace("*", "").replace("#", "").strip()
            if not texto_final:
                texto_final = "Operación completada, señor."
            return texto_final, True
        except Exception as e:
            print(f"[Cerebro LLM Aviso]: {e}. Usando respaldo local.")
            return self._respaldo_local(cmd_low), True

    def _respaldo_local(self, comando: str) -> str:
        if any(k in comando for k in ("pantalla", "mira esto", "qué ves")):
            ruta = capturar_pantalla_actual()
            return analizar_imagen_con_gemini(ruta, comando) if ruta else "Error al capturar pantalla."
        if any(k in comando for k in ("orden del día", "pendientes", "agenda", "suma")):
            return self.sys.construir_orden_del_dia()
        if any(k in comando for k in ("háblame", "hablame", "dime algo")):
            return random.choice(self.sys.FRASES_INTERACTIVAS)
        if "siguiente canción" in comando or "otra rola" in comando:
            self.sys.ejecutar_seguro(["playerctl", "--player=spotify", "next"])
            return "Cambiando de pista, señor."
        if "pausa" in comando:
            self.sys.ejecutar_seguro(["playerctl", "--player=spotify", "pause"])
            return "Música en pausa, señor."
        if "reproduce" in comando or "pon música" in comando:
            self.sys.reproducir_musica_aleatoria()
            return "Reproduciendo música en Spotify, señor."
        if "portapapeles" in comando:
            return self.sys.leer_portapapeles()
        return "Instrucción procesada en modo local, señor."
