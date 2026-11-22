#!/usr/bin/env python3
"""
J.A.R.V.I.S. - HUD Holográfico Mark XIV
- Animaciones cinemáticas de ENTRADA (Materialización Láser y Expansión Radial) y de CIERRE (Colapso al Núcleo)
- Márgenes responsivos corregidos en Pantalla Completa para que ningún panel se corte en los bordes
- Animación de Portal Holográfico cada vez que abre/cierra apps, genera Dossiers o proyecta Modelos 3D
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import os
os.environ["QT_QPA_PLATFORM"] = "xcb"

import datetime
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import psutil
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QKeySequence, QPainter, QPen, QRadialGradient, QShortcut
from PySide6.QtWidgets import QApplication, QWidget

from jarvis_memory import depurar_y_actualizar_todo_el_contexto

ARCHIVO_ESTADO_HUD = Path("/tmp/jarvis_hud_state.json")
ARCHIVO_AGENDA = Path.home() / "jarvis" / "agenda.json"


def leer_estado_hud_actual() -> dict:
    if ARCHIVO_ESTADO_HUD.exists():
        try:
            return json.loads(ARCHIVO_ESTADO_HUD.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def escribir_estado_hud(
    estado: str,
    subtexto: str = "",
    visible: bool = True,
    animacion: str = "NORMAL",
    app_actual: str = "",
    progreso: int = 0,
    cuadrante: int = 0,
    fullscreen: bool | None = None,
    silenciado: bool | None = None,
    grabando: bool | None = None,
    efecto_transicion: str = "",
) -> None:
    prev = leer_estado_hud_actual()
    datos = {
        "estado": estado,
        "subtexto": subtexto[:165] + "..." if len(subtexto) > 165 else subtexto,
        "visible": visible,
        "animacion": animacion,
        "app_actual": app_actual,
        "progreso": max(0, min(100, progreso)),
        "cuadrante": cuadrante,
        "fullscreen": prev.get("fullscreen", False) if fullscreen is None else fullscreen,
        "silenciado": prev.get("silenciado", False) if silenciado is None else silenciado,
        "grabando": prev.get("grabando", False) if grabando is None else grabando,
        "efecto_transicion": efecto_transicion,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S.%f"),
    }
    try:
        ARCHIVO_ESTADO_HUD.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class JarvisHologramHUD(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. MARK XIV — HOLOGRAPHIC COMMAND CENTER")

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_esc.activated.connect(self.iniciar_cierre_pantalla_completa)

        self.modo_pantalla_completa = False
        self.modo_mini = False
        self.modo_silenciado = False
        self.grabando_video = False
        self.posicion_guardada: QPoint | None = None
        self._press_global_pos: QPoint | None = None
        self._window_pos_at_press: QPoint | None = None
        self._movio_en_arrastre = False

        # Motor de Animación Holográfica de Entrada y Salida (0.0 = colapsado, 1.0 = desplegado total)
        self.fase_apertura = 0.02
        self.direccion_transicion = 1       # +1 = abriendo/materializando, -1 = cerrando/colapsando, 0 = estable
        self.accion_post_colapso = None     # callback tras terminar animación de cierre
        self.onda_portal_radio = 0.0        # Onda expansiva al abrir apps / 3D / Dossiers
        self.onda_portal_activa = False
        self.etiqueta_portal = ""
        self.ultimo_ts_leido = ""

        self.rect_reactor = QRectF(25, 35, 100, 100)
        self.rect_btn_mute = QRectF(145, 8, 92, 22)
        self.rect_btn_full = QRectF(242, 8, 112, 22)
        self.rect_btn_mini = QRectF(360, 8, 28, 22)

        self.angulo_1 = 0.0
        self.angulo_2 = 360.0
        self.angulo_3 = 180.0
        self.pulso = 0.0
        self.scan_line_y = 0.0

        self.estado_actual = "EN LÍNEA"
        self.animacion_actual = "NORMAL"
        self.subtexto = "Sistemas Holográficos Mark XIV en línea."
        self.app_actual = ""
        self.progreso = 0
        self.cuadrante = 0

        self.cpu_pct = 0
        self.ram_pct = 0
        self.gpu_temp = "--"
        self.bat_pct = 100
        self.perfil_energia = "BALANCEADO"
        self.pendientes_top = []
        self.memoria_cache = depurar_y_actualizar_todo_el_contexto()

        self.aplicar_geometria_actual(conservar_pos=False)
        self.disparar_animacion_entrada("MATERIALIZANDO NÚCLEO HOLOGRÁFICO J.A.R.V.I.S.")

        self.timer_anim = QTimer(self)
        self.timer_anim.timeout.connect(self.actualizar_animacion)
        self.timer_anim.start(25)  # 40 FPS fluidos

        self.timer_telemetria = QTimer(self)
        self.timer_telemetria.timeout.connect(self.actualizar_telemetria)
        self.timer_telemetria.start(2200)
        self.actualizar_telemetria()

    def disparar_animacion_entrada(self, etiqueta: str = "") -> None:
        self.fase_apertura = 0.04
        self.direccion_transicion = 1
        self.accion_post_colapso = None
        if etiqueta:
            self.disparar_onda_portal(etiqueta)

    def disparar_animacion_cierre(self, callback_final) -> None:
        self.fase_apertura = 0.98
        self.direccion_transicion = -1
        self.accion_post_colapso = callback_final

    def disparar_onda_portal(self, texto_portal: str) -> None:
        self.onda_portal_radio = 10.0
        self.onda_portal_activa = True
        self.etiqueta_portal = texto_portal

    def obtener_temperatura_sistema(self) -> str:
        if shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL, text=True, timeout=1.0,
                ).strip()
                if out.isdigit():
                    return f"{out}°C"
            except Exception:
                pass
        try:
            temps = psutil.sensors_temperatures()
            for clave in ("nvme", "coretemp", "k10temp", "acpitz", "asus"):
                if clave in temps and temps[clave]:
                    return f"{round(temps[clave][0].current)}°C"
            for lista in temps.values():
                if lista:
                    return f"{round(lista[0].current)}°C"
        except Exception:
            pass
        return "45°C"

    def aplicar_geometria_actual(self, conservar_pos: bool = True) -> None:
        avail = QApplication.primaryScreen().availableGeometry()

        if self.modo_pantalla_completa:
            # Usar availableGeometry() para que NUNCA se corte por el Dock o bordes del monitor
            self.setMinimumSize(avail.width(), avail.height())
            self.setMaximumSize(avail.width(), avail.height())
            self.setGeometry(avail)
            self.showNormal()
            self.raise_()
        else:
            self.showNormal()
            w, h = (280, 150) if self.modo_mini else (400, 485)
            self.setMinimumSize(w, h)
            self.setMaximumSize(w, h)
            self.resize(w, h)
            if conservar_pos and self.posicion_guardada is not None:
                self.move(self.posicion_guardada)
            else:
                pos_ini = QPoint(avail.x() + avail.width() - w - 20, avail.y() + 20)
                self.posicion_guardada = pos_ini
                self.move(pos_ini)

    def alternar_pantalla_completa(self) -> None:
        if self.modo_pantalla_completa:
            self.iniciar_cierre_pantalla_completa()
        else:
            self.modo_pantalla_completa = True
            escribir_estado_hud(
                self.estado_actual, self.subtexto, visible=True,
                animacion=self.animacion_actual, app_actual=self.app_actual,
                progreso=self.progreso, cuadrante=self.cuadrante, fullscreen=True,
            )
            self.aplicar_geometria_actual(conservar_pos=True)
            self.disparar_animacion_entrada("DESPLEGANDO CENTRO DE COMANDO INTEGRAL")

    def iniciar_cierre_pantalla_completa(self) -> None:
        if self.modo_pantalla_completa:
            def _fin_colapso():
                self.modo_pantalla_completa = False
                escribir_estado_hud(self.estado_actual, self.subtexto, fullscreen=False)
                self.aplicar_geometria_actual(conservar_pos=True)
                self.disparar_animacion_entrada()
            self.disparar_animacion_cierre(_fin_colapso)

    def alternar_modo_silencio(self) -> None:
        self.modo_silenciado = not self.modo_silenciado
        nuevo_estado = "SUSPENDIDO (CLASE SUMA)" if self.modo_silenciado else "EN LÍNEA"
        nuevo_sub = (
            "Modo No Molestar activo. Diga 'Jarvis despierta' o pulse [🔊] para reactivar."
            if self.modo_silenciado
            else "Sistemas reactivados. A sus órdenes, señor."
        )
        escribir_estado_hud(
            nuevo_estado, nuevo_sub, visible=True,
            animacion="STEALTH" if self.modo_silenciado else "NORMAL",
            silenciado=self.modo_silenciado,
        )
        self.disparar_onda_portal("MODO SILENCIO ACTIVADO" if self.modo_silenciado else "SISTEMAS REACTIVADOS")
        self.update()

    def obtener_color_tema(self) -> QColor:
        if self.modo_silenciado:
            return QColor(90, 130, 165)
        if self.animacion_actual == "LOW_BATTERY":
            brillo = int(120 + 110 * math.sin(self.pulso * 2.5))
            return QColor(brillo, 35, 20)
        if self.animacion_actual == "RECORDING":
            return QColor(255, 75, 95)
        if self.animacion_actual in ("DEMO", "BOOT_LOGIN"):
            fase = (math.sin(self.pulso * 1.5) + 1) / 2
            return QColor(int(0 + 240 * fase), int(235 - 30 * fase), int(255 - 180 * fase))
        if self.animacion_actual == "POWER_SAVE":
            return QColor(0, 235, 160)
        if self.animacion_actual == "CLOSE_ALL":
            return QColor(255, 80, 80)
        if self.animacion_actual == "RESEARCH":
            return QColor(165, 115, 255)

        mapa = {
            "EN LÍNEA": QColor(0, 230, 255),
            "ESCUCHANDO": QColor(0, 255, 145),
            "PROCESANDO": QColor(255, 195, 0),
            "HABLANDO": QColor(65, 185, 255),
            "ALERTA": QColor(255, 65, 65),
        }
        return mapa.get(self.estado_actual, QColor(0, 230, 255))

    def actualizar_animacion(self) -> None:
        # 1. Evolución de la transición de Entrada / Cierre
        if self.direccion_transicion == 1:
            self.fase_apertura = min(1.0, self.fase_apertura + 0.065)
            if self.fase_apertura >= 1.0:
                self.direccion_transicion = 0
        elif self.direccion_transicion == -1:
            self.fase_apertura = max(0.02, self.fase_apertura - 0.085)
            if self.fase_apertura <= 0.04:
                self.direccion_transicion = 0
                if self.accion_post_colapso:
                    cb = self.accion_post_colapso
                    self.accion_post_colapso = None
                    cb()

        # 2. Evolución de la Onda de Portal Holográfico (al abrir/cerrar apps, 3D o Dossiers)
        if self.onda_portal_activa:
            max_r = max(self.width(), self.height()) * 0.75
            self.onda_portal_radio += max(14.0, max_r * 0.055)
            if self.onda_portal_radio >= max_r:
                self.onda_portal_activa = False

        vel = 0.5 if self.modo_silenciado else (7.2 if self.direccion_transicion != 0 or self.onda_portal_activa or self.animacion_actual in ("APP_LAUNCH", "DEMO", "BOOT_LOGIN", "RESEARCH", "CLOSE_ALL", "RECORDING") else 2.2)
        self.angulo_1 = (self.angulo_1 + vel) % 360
        self.angulo_2 = (self.angulo_2 - vel * 1.45) % 360
        self.angulo_3 = (self.angulo_3 + vel * 0.9) % 360
        self.pulso = (self.pulso + 0.16) % (2 * math.pi)
        self.scan_line_y = (self.scan_line_y + 9.0) % max(1, self.height())

        if ARCHIVO_ESTADO_HUD.exists():
            try:
                datos = json.loads(ARCHIVO_ESTADO_HUD.read_text(encoding="utf-8"))
                ts = datos.get("timestamp", "")
                anim_nueva = datos.get("animacion", "NORMAL")
                efecto = datos.get("efecto_transicion", "")

                if ts != self.ultimo_ts_leido:
                    self.ultimo_ts_leido = ts
                    if efecto == "ENTRADA" or (anim_nueva in ("BOOT_LOGIN", "APP_LAUNCH", "RESEARCH") and anim_nueva != self.animacion_actual):
                        self.disparar_animacion_entrada(datos.get("app_actual", "PROYECTANDO HOLOGRAMA"))
                    elif efecto == "PORTAL":
                        self.disparar_onda_portal(datos.get("app_actual", "EJECUTANDO MÓDULO"))
                    elif efecto == "CIERRE" or (anim_nueva == "CLOSE_ALL" and self.animacion_actual != "CLOSE_ALL"):
                        self.disparar_onda_portal("COLAPSANDO VENTANAS // CIERRE HOLOGRÁFICO")

                self.estado_actual = datos.get("estado", self.estado_actual)
                self.subtexto = datos.get("subtexto", self.subtexto)
                self.animacion_actual = anim_nueva
                self.app_actual = datos.get("app_actual", "")
                self.progreso = int(datos.get("progreso", 0))
                self.cuadrante = int(datos.get("cuadrante", 0))
                self.modo_silenciado = bool(datos.get("silenciado", False))
                self.grabando_video = bool(datos.get("grabando", False)) or (self.animacion_actual == "RECORDING")

                fs_solicitado = bool(datos.get("fullscreen", False)) or (self.animacion_actual in ("BOOT_LOGIN", "DEMO"))
                if fs_solicitado != self.modo_pantalla_completa and self.direccion_transicion == 0:
                    self.modo_pantalla_completa = fs_solicitado
                    self.aplicar_geometria_actual(conservar_pos=True)
                    self.disparar_animacion_entrada("INICIALIZANDO INTERFAZ STARK")

                vis = datos.get("visible", True)
                if not vis and self.isVisible():
                    self.hide()
                elif vis and not self.isVisible():
                    self.show()
                    self.disparar_animacion_entrada()
            except Exception:
                pass

        self.update()

    def actualizar_telemetria(self) -> None:
        self.cpu_pct = round(psutil.cpu_percent())
        self.ram_pct = round(psutil.virtual_memory().percent)
        bat = psutil.sensors_battery()
        self.bat_pct = round(bat.percent) if bat else 100
        self.gpu_temp = self.obtener_temperatura_sistema()
        self.memoria_cache = depurar_y_actualizar_todo_el_contexto()

        if shutil.which("powerprofilesctl"):
            try:
                p_out = subprocess.check_output(["powerprofilesctl", "get"], text=True, stderr=subprocess.DEVNULL).strip().lower()
                if "power-saver" in p_out:
                    self.perfil_energia = "AHORRO BATERÍA"
                elif "performance" in p_out:
                    self.perfil_energia = "TURBO RENDIMIENTO"
                else:
                    self.perfil_energia = "BALANCEADO"
            except Exception:
                pass

        if ARCHIVO_AGENDA.exists():
            try:
                ag = json.loads(ARCHIVO_AGENDA.read_text(encoding="utf-8"))
                activos = [p for p in ag.get("pendientes", []) if not p.get("completado", False)]
                self.pendientes_top = [f"[{p['categoria']}] {p['titulo']}" for p in activos[:4]]
            except Exception:
                pass

    def dibujar_reactor_stark(self, painter: QPainter, cx: int, cy: int, r_max: int, color_t: QColor) -> None:
        r_ef = max(8, int(r_max * (0.25 + 0.75 * self.fase_apertura)))
        self.rect_reactor = QRectF(cx - r_max, cy - r_max, r_max * 2, r_max * 2)
        escala = 1.0 + 0.12 * math.sin(self.pulso)
        grad = QRadialGradient(cx, cy, int(r_ef * 0.88 * escala))
        grad.setColorAt(0.0, QColor(color_t.red(), color_t.green(), color_t.blue(), 240))
        grad.setColorAt(0.45, QColor(color_t.red(), color_t.green(), color_t.blue(), 100))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(r_ef * 0.88 * escala), int(r_ef * 0.88 * escala))

        sweep_factor = self.fase_apertura

        # Anillo 1 exterior segmentado
        painter.setPen(QPen(color_t, 3.5))
        rect1 = QRectF(cx - r_ef, cy - r_ef, r_ef * 2, r_ef * 2)
        for i in range(4):
            painter.drawArc(rect1, int((self.angulo_1 + i * 90) * 16), int(58 * sweep_factor * 16))

        # Anillo 2 medio dorado/cian
        r2 = int(r_ef * 0.74)
        painter.setPen(QPen(QColor(255, 215, 75, int(225 * sweep_factor)), 2.4))
        rect2 = QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2)
        for i in range(3):
            painter.drawArc(rect2, int((self.angulo_2 + i * 120) * 16), int(78 * sweep_factor * 16))

        # Anillo 3 interno
        r3 = int(r_ef * 0.48)
        painter.setPen(QPen(QColor(210, 250, 255, int(225 * sweep_factor)), 2.0))
        rect3 = QRectF(cx - r3, cy - r3, r3 * 2, r3 * 2)
        for i in range(2):
            painter.drawArc(rect3, int((self.angulo_3 + i * 180) * 16), int(115 * sweep_factor * 16))

        painter.setPen(QPen(QColor(255, 255, 255, int(220 * sweep_factor)), 1.6))
        r_core = max(3, int(r_ef * 0.22))
        painter.drawEllipse(QPoint(cx, cy), r_core, r_core)

        # Onda de Portal Holográfico cuando abre/cierra apps, 3D o Dossiers
        if self.onda_portal_activa:
            op_onda = max(0, min(220, int(220 * (1.0 - self.onda_portal_radio / (max(self.width(), self.height()) * 0.75)))))
            painter.setPen(QPen(QColor(255, 215, 75, op_onda), 2.5, Qt.PenStyle.DashDotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r_onda = int(self.onda_portal_radio)
            painter.drawEllipse(QPoint(cx, cy), r_onda, r_onda)

    def dibujar_corchetes_holograficos(self, painter: QPainter, x: float, y: float, w: float, h: float, color_t: QColor) -> None:
        """Dibuja esquinas tácticas estilo visor Iron Man en los paneles."""
        L = min(18.0, w * 0.08, h * 0.15)
        painter.setPen(QPen(QColor(255, 215, 75, int(210 * self.fase_apertura)), 2.2))
        # Arriba Izq
        painter.drawLine(int(x), int(y), int(x + L), int(y))
        painter.drawLine(int(x), int(y), int(x), int(y + L))
        # Arriba Der
        painter.drawLine(int(x + w - L), int(y), int(x + w), int(y))
        painter.drawLine(int(x + w), int(y), int(x + w), int(y + L))
        # Abajo Izq
        painter.drawLine(int(x), int(y + h - L), int(x), int(y + h))
        painter.drawLine(int(x), int(y + h), int(x + L), int(y + h))
        # Abajo Der
        painter.drawLine(int(x + w - L), int(y + h), int(x + w), int(y + h))
        painter.drawLine(int(x + w), int(y + h - L), int(x + w), int(y + h))

    def dibujar_anillo_simetrico(self, painter: QPainter, x: int, y: int, w: int, h: int, color_t: QColor) -> None:
        painter.setPen(QPen(color_t, 1.5))
        painter.setBrush(QColor(8, 22, 40, int(175 * self.fase_apertura)))
        painter.drawRoundedRect(QRectF(x, y, w, h), 8, 8)
        self.dibujar_corchetes_holograficos(painter, x, y, w, h, color_t)

        sectores_coords = [
            (x + 10, y + 10, w * 0.47, h * 0.42, "CUADRANTE 1: GEMINI / WEB"),
            (x + w * 0.51, y + 10, w * 0.47, h * 0.42, "CUADRANTE 2: VS CODE IDE"),
            (x + 10, y + h * 0.53, w * 0.47, h * 0.42, "CUADRANTE 3: WHATSAPP / COMMS"),
            (x + w * 0.51, y + h * 0.53, w * 0.47, h * 0.42, "CUADRANTE 4: INGENIERÍA / 3D"),
        ]
        for idx, (sx, sy, sw, sh, nombre_s) in enumerate(sectores_coords, start=1):
            activo = (self.cuadrante == idx) or (self.progreso >= 95)
            if activo:
                painter.setBrush(QColor(color_t.red(), color_t.green(), color_t.blue(), int(125 * self.fase_apertura)))
                painter.setPen(QPen(QColor(255, 220, 80, int(240 * self.fase_apertura)), 2.0))
            else:
                painter.setBrush(QColor(15, 35, 55, int(110 * self.fase_apertura)))
                painter.setPen(QPen(QColor(color_t.red(), color_t.green(), color_t.blue(), int(85 * self.fase_apertura)), 1.0))
            painter.drawRoundedRect(QRectF(sx, sy, sw, sh), 5, 5)
            painter.setFont(QFont("Ubuntu Mono", 8, QFont.Weight.Bold))
            painter.drawText(int(sx + 8), int(sy + 22), nombre_s)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(max(0.08, self.fase_apertura))
        color_t = self.obtener_color_tema()

        if self.modo_pantalla_completa:
            w, h = self.width(), self.height()
            pad_x = max(24, int(w * 0.022))  # Margen seguro adaptable para evitar cortes en los bordes

            painter.setBrush(QColor(4, 10, 20, 242))
            painter.setPen(QPen(color_t, 2.5))
            painter.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), 14, 14)

            # Barrido láser horizontal de escaneo holográfico
            painter.setPen(QPen(QColor(color_t.red(), color_t.green(), color_t.blue(), 75), 2.2))
            painter.drawLine(8, int(self.scan_line_y), w - 8, int(self.scan_line_y))

            # Botón superior derecho con margen seguro
            self.rect_btn_full = QRectF(w - pad_x - 245, 20, 245, 34)
            painter.setBrush(QColor(0, 80, 120, 195))
            painter.setPen(QPen(QColor(255, 215, 70), 1.8))
            painter.drawRoundedRect(self.rect_btn_full, 8, 8)
            painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
            painter.setPen(QColor(255, 235, 130))
            painter.drawText(self.rect_btn_full, Qt.AlignmentFlag.AlignCenter, "[ ❐ COLAPSAR A VENTANA (ESC) ]")

            painter.setPen(color_t)
            painter.setFont(QFont("Ubuntu", 17, QFont.Weight.Bold))
            titulo_fs = (
                "STARK INDUSTRIES // PROTOCOLO SHOWSTOPPER MARK XIV"
                if self.animacion_actual == "BOOT_LOGIN"
                else "J.A.R.V.I.S. MARK XIV // CENTRO DE COMANDO HOLOGRÁFICO INTEGRAL"
            )
            painter.drawText(pad_x, 44, titulo_fs)

            painter.setPen(QColor(190, 235, 255))
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            ahora_str = datetime.datetime.now().strftime("%d/%m/%Y | %H:%M:%S CST | COYOACÁN, CDMX")
            rec_tag = " // [ 🔴 REC ]" if self.grabando_video else ""
            painter.drawText(pad_x, 68, f"ING. LUIS MAXIMILIANO GUZMÁN ORTIZ (MAX) // ENERGÍA: {self.perfil_energia}{rec_tag} // {ahora_str}")

            cx, cy = w // 2, int(h * 0.37)
            r_gigante = min(145, int(h * 0.17))
            self.dibujar_reactor_stark(painter, cx, cy, r_gigante, color_t)

            painter.setPen(QColor(255, 215, 75))
            painter.setFont(QFont("Ubuntu Mono", 12, QFont.Weight.Bold))
            mod_txt = self.app_actual if self.app_actual else f"ESTADO DEL NÚCLEO: {self.estado_actual}"
            rect_mod = QRectF(cx - 290, cy + r_gigante + 10, 580, 26)
            painter.drawText(rect_mod, Qt.AlignmentFlag.AlignCenter, f"» {mod_txt} «")

            painter.setPen(QColor(215, 245, 255))
            painter.setFont(QFont("Ubuntu", 10))
            rect_sub = QRectF(cx - 310, cy + r_gigante + 36, 620, 48)
            painter.drawText(rect_sub, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.subtexto)

            if self.progreso > 0:
                bx, by, bw, bh = cx - 230, cy + r_gigante + 86, 460, 14
                painter.setBrush(QColor(15, 40, 68, 200))
                painter.setPen(QPen(color_t, 1.2))
                painter.drawRoundedRect(QRectF(bx, by, bw, bh), 5, 5)
                painter.setBrush(color_t)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(bx, by, max(10, int(bw * self.progreso / 100)), bh), 5, 5)

            # Deslizamiento cinemático de los paneles laterales durante la entrada/salida
            offset_slide = int((1.0 - self.fase_apertura) * 140)
            col_w = int(w * 0.275)
            col_izq_x = pad_x - offset_slide
            col_der_x = w - col_w - pad_x + offset_slide

            p1_y = 96
            painter.setBrush(QColor(10, 24, 44, 190))
            painter.setPen(QPen(color_t, 1.5))
            painter.drawRoundedRect(QRectF(col_izq_x, p1_y, col_w, 168), 12, 12)
            self.dibujar_corchetes_holograficos(painter, col_izq_x, p1_y, col_w, 168, color_t)
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            painter.drawText(col_izq_x + 14, p1_y + 24, f"⚡ TELEMETRÍA ({self.perfil_energia})")

            yb = p1_y + 42
            for etq, val in [("CPU CORE", self.cpu_pct), ("RAM MEM", self.ram_pct), ("BATERÍA", self.bat_pct)]:
                painter.setPen(QColor(190, 230, 250))
                painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
                painter.drawText(col_izq_x + 14, yb + 11, etq)
                painter.setBrush(QColor(25, 48, 72, 200))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(QRectF(col_izq_x + 90, yb, col_w - 155, 12), 4, 4)
                painter.setBrush(color_t)
                painter.drawRoundedRect(QRectF(col_izq_x + 90, yb, max(6, int((col_w - 155) * val / 100)), 12), 4, 4)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(col_izq_x + col_w - 55, yb + 11, f"{val}%")
                yb += 26
            painter.setPen(QColor(255, 215, 75))
            painter.drawText(col_izq_x + 14, yb + 14, f"SENSOR TÉRMICO GPU/NÚCLEO: {self.gpu_temp}")

            p2_y = 280
            painter.setBrush(QColor(10, 24, 44, 190))
            painter.setPen(QPen(color_t, 1.5))
            painter.drawRoundedRect(QRectF(col_izq_x, p2_y, col_w, 195), 12, 12)
            self.dibujar_corchetes_holograficos(painter, col_izq_x, p2_y, col_w, 195, color_t)
            painter.setPen(QColor(255, 215, 70))
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            painter.drawText(col_izq_x + 14, p2_y + 24, "🎓 CLASSROOM (VIGENTES SIN ENTREGAR)")

            yc = p2_y + 44
            cr_activas = self.memoria_cache.get("classroom_asignaciones", [])
            if not cr_activas:
                painter.setPen(QColor(0, 255, 170))
                painter.setFont(QFont("Ubuntu", 9, QFont.Weight.Bold))
                painter.drawText(col_izq_x + 14, yc + 12, "✓ Todas las asignaciones entregadas y al día.")
            else:
                for asig in cr_activas[:3]:
                    painter.setPen(QColor(0, 240, 255))
                    painter.setFont(QFont("Ubuntu", 8.5, QFont.Weight.Bold))
                    painter.drawText(col_izq_x + 14, yc, f"• {asig['curso'][:42]}")
                    yc += 16
                    painter.setPen(QColor(230, 245, 255))
                    painter.setFont(QFont("Ubuntu", 8.5))
                    painter.drawText(col_izq_x + 20, yc, f"{asig['titulo'][:46]}")
                    yc += 15
                    painter.setPen(QColor(255, 160, 90))
                    painter.setFont(QFont("Ubuntu Mono", 8, QFont.Weight.Bold))
                    painter.drawText(col_izq_x + 20, yc, f"Vence: {asig.get('entrega_humana', asig['entrega'])}")
                    yc += 20

            p3_y = 490
            p3_h = max(130, h - p3_y - 24)
            painter.setBrush(QColor(10, 24, 44, 190))
            painter.setPen(QPen(color_t, 1.5))
            painter.drawRoundedRect(QRectF(col_izq_x, p3_y, col_w, p3_h), 12, 12)
            self.dibujar_corchetes_holograficos(painter, col_izq_x, p3_y, col_w, p3_h, color_t)
            painter.setPen(color_t)
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            painter.drawText(col_izq_x + 14, p3_y + 24, "📋 PENDIENTES Y PROYECTOS VIGENTES")
            yp = p3_y + 46
            painter.setPen(QColor(215, 240, 255))
            painter.setFont(QFont("Ubuntu", 8.5))
            for item in self.pendientes_top:
                painter.drawText(col_izq_x + 14, yp, f"▸ {item[:48]}")
                yp += 22

            # Paneles Derechos con margen seguro
            painter.setBrush(QColor(10, 24, 44, 190))
            painter.setPen(QPen(color_t, 1.5))
            painter.drawRoundedRect(QRectF(col_der_x, p1_y, col_w, 265), 12, 12)
            self.dibujar_corchetes_holograficos(painter, col_der_x, p1_y, col_w, 265, color_t)
            painter.setPen(QColor(255, 215, 70))
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            painter.drawText(col_der_x + 14, p1_y + 24, "✉️ CORREOS Y MENSAJES POR ATENDER")

            ym = p1_y + 46
            for corr in self.memoria_cache.get("correos_importantes", [])[:4]:
                painter.setPen(QColor(0, 240, 255))
                painter.setFont(QFont("Ubuntu", 8.5, QFont.Weight.Bold))
                painter.drawText(col_der_x + 14, ym, f"• {corr['remitente'][:40]}")
                ym += 16
                painter.setPen(QColor(235, 245, 255))
                painter.setFont(QFont("Ubuntu", 8.5))
                painter.drawText(col_der_x + 20, ym, f"{corr['asunto'][:46]}")
                ym += 15
                painter.setPen(QColor(165, 205, 230))
                painter.setFont(QFont("Ubuntu", 8))
                painter.drawText(col_der_x + 20, ym, f"{corr['resumen'][:48]}...")
                ym += 20

            p5_y = 378
            p5_h = max(180, h - p5_y - 24)
            painter.setBrush(QColor(10, 24, 44, 190))
            painter.setPen(QPen(color_t, 1.5))
            painter.drawRoundedRect(QRectF(col_der_x, p5_y, col_w, p5_h), 12, 12)
            self.dibujar_corchetes_holograficos(painter, col_der_x, p5_y, col_w, p5_h, color_t)
            painter.setPen(color_t)
            painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
            painter.drawText(col_der_x + 14, p5_y + 24, "🧠 MEMORIA NEURONAL (SOREN ALESSA & EQUIPO)")

            yn = p5_y + 46
            for p_info in list(self.memoria_cache.get("personas", {}).values())[:5]:
                painter.setPen(QColor(255, 215, 75))
                painter.setFont(QFont("Ubuntu", 8.5, QFont.Weight.Bold))
                painter.drawText(col_der_x + 14, yn, f"• {p_info['nombre']}:")
                yn += 15
                painter.setPen(QColor(210, 235, 250))
                painter.setFont(QFont("Ubuntu", 8))
                painter.drawText(col_der_x + 20, yn, f"{p_info['relacion'][:50]}")
                yn += 19

            mapa_w = int(w * 0.31)
            mapa_h = 148
            mapa_x = (w - mapa_w) // 2
            mapa_y = h - mapa_h - 24
            self.dibujar_anillo_simetrico(painter, mapa_x, mapa_y, mapa_w, mapa_h, color_t)
            return

        # =====================================================================
        # MODO VENTANA COMPACTA MOVIBLE CON ESCALADO DE ENTRADA/SALIDA
        # =====================================================================
        w_c, h_c = self.width(), self.height()
        margen_anim = int((1.0 - self.fase_apertura) * 40)
        rect_ventana = QRectF(4 + margen_anim, 4 + margen_anim, w_c - 8 - 2 * margen_anim, h_c - 8 - 2 * margen_anim)

        painter.setBrush(QColor(6, 14, 26, 235))
        painter.setPen(QPen(QColor(color_t.red(), color_t.green(), color_t.blue(), 195), 2.0))
        painter.drawRoundedRect(rect_ventana, 16, 16)
        self.dibujar_corchetes_holograficos(painter, rect_ventana.x(), rect_ventana.y(), rect_ventana.width(), rect_ventana.height(), color_t)

        # Línea láser de escaneo en el HUD compacto
        painter.setPen(QPen(QColor(color_t.red(), color_t.green(), color_t.blue(), 45), 1.5))
        painter.drawLine(int(rect_ventana.left() + 4), int(self.scan_line_y), int(rect_ventana.right() - 4), int(self.scan_line_y))

        painter.setBrush(QColor(12, 32, 56, 210))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(6, 6, w_c - 12, 28), 12, 12)

        painter.setPen(QColor(255, 80, 90) if self.grabando_video else QColor(150, 215, 245))
        painter.setFont(QFont("Ubuntu Mono", 8, QFont.Weight.Bold))
        etq_top = "🔴 REC" if self.grabando_video else ("" if self.modo_mini else "✥ MOVER")
        painter.drawText(14, 24, etq_top)

        self.rect_btn_mute = QRectF(w_c - 256, 8, 96, 22)
        painter.setBrush(QColor(160, 45, 45, 210) if self.modo_silenciado else QColor(15, 75, 110, 200))
        painter.setPen(QPen(QColor(255, 180, 90) if self.modo_silenciado else color_t, 1.1))
        painter.drawRoundedRect(self.rect_btn_mute, 5, 5)
        painter.setPen(QColor(255, 235, 200))
        painter.setFont(QFont("Ubuntu Mono", 7, QFont.Weight.Bold))
        painter.drawText(self.rect_btn_mute, Qt.AlignmentFlag.AlignCenter, "🔊 DESPERTAR" if self.modo_silenciado else "🔇 SILENCIAR")

        self.rect_btn_full = QRectF(w_c - 154, 8, 112, 22)
        painter.setBrush(QColor(0, 110, 160, 200))
        painter.setPen(QPen(QColor(255, 215, 70), 1.2))
        painter.drawRoundedRect(self.rect_btn_full, 5, 5)
        painter.setPen(QColor(255, 235, 140))
        painter.setFont(QFont("Ubuntu Mono", 7, QFont.Weight.Bold))
        painter.drawText(self.rect_btn_full, Qt.AlignmentFlag.AlignCenter, "⛶ FULLSCREEN")

        self.rect_btn_mini = QRectF(w_c - 36, 8, 26, 22)
        painter.setBrush(QColor(20, 60, 95, 200))
        painter.setPen(QPen(color_t, 1.0))
        painter.drawRoundedRect(self.rect_btn_mini, 5, 5)
        painter.setPen(color_t)
        painter.drawText(self.rect_btn_mini, Qt.AlignmentFlag.AlignCenter, "—" if not self.modo_mini else "+")

        if self.modo_mini:
            self.dibujar_reactor_stark(painter, 52, 85, 34, color_t)
            painter.setPen(color_t)
            painter.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
            painter.drawText(100, 62, "J.A.R.V.I.S. MARK XIV")
            painter.setPen(QColor(210, 240, 255))
            painter.setFont(QFont("Ubuntu Mono", 8))
            painter.drawText(100, 84, f"CPU:{self.cpu_pct}% BAT:{self.bat_pct}% ({self.perfil_energia[:6]})")
            painter.setPen(QColor(255, 215, 70))
            painter.drawText(100, 104, self.etiqueta_portal[:22] if self.onda_portal_activa else ("1 Clic Reactor: Fullscreen"))
            return

        self.dibujar_reactor_stark(painter, 76, 94, 45, color_t)

        painter.setPen(color_t)
        painter.setFont(QFont("Ubuntu", 11, QFont.Weight.Bold))
        painter.drawText(140, 58, f"J.A.R.V.I.S.  MARK XIV [{self.perfil_energia[:6]}]")

        painter.setPen(QColor(210, 240, 255))
        painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
        painter.drawText(140, 78, datetime.datetime.now().strftime("%H:%M:%S | CDMX"))

        painter.setPen(color_t)
        painter.setFont(QFont("Ubuntu", 9, QFont.Weight.Bold))
        status_str = "🔴 GRABANDO VIDEOCLIP" if self.grabando_video else ("MODO SILENCIO (SUMA)" if self.modo_silenciado else self.estado_actual)
        painter.drawText(140, 98, f"STATUS: {status_str}")

        painter.setPen(QColor(255, 215, 75))
        painter.setFont(QFont("Ubuntu", 8, QFont.Weight.Bold))
        painter.drawText(140, 116, "⚡ Clic en Reactor: Pantalla Completa")

        painter.setPen(QColor(185, 220, 245))
        painter.setFont(QFont("Ubuntu", 9))
        painter.drawText(QRectF(20, 148, 360, 40), Qt.TextFlag.TextWordWrap, f"» {self.subtexto}")

        y_base = 200
        for etiqueta, valor, texto_val in [
            ("CPU", self.cpu_pct, f"{self.cpu_pct}%"),
            ("RAM", self.ram_pct, f"{self.ram_pct}%"),
            ("BAT", self.bat_pct, f"{self.bat_pct}%"),
        ]:
            painter.setPen(QColor(180, 220, 240))
            painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
            painter.drawText(20, y_base + 11, etiqueta)

            painter.setBrush(QColor(25, 45, 68, 190))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(62, y_base, 245, 12), 4, 4)

            ancho_val = max(4, int(2.45 * min(100, valor) * self.fase_apertura))
            painter.setBrush(color_t)
            painter.drawRoundedRect(QRectF(62, y_base, ancho_val, 12), 4, 4)

            painter.setPen(QColor(225, 245, 255))
            painter.drawText(318, y_base + 11, texto_val)
            y_base += 24

        painter.setPen(color_t)
        painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
        painter.drawText(20, y_base + 12, f"TEMP: {self.gpu_temp}  |  MODO: {self.perfil_energia}")

        y_cr = y_base + 32
        painter.setPen(QColor(255, 215, 70))
        painter.setFont(QFont("Ubuntu", 8, QFont.Weight.Bold))
        painter.drawText(20, y_cr, "CLASSROOM (PENDIENTES POR ENTREGAR):")
        y_cr += 16
        painter.setPen(QColor(215, 240, 255))
        painter.setFont(QFont("Ubuntu", 8))
        cr_act = self.memoria_cache.get("classroom_asignaciones", [])
        if not cr_act:
            painter.drawText(20, y_cr, "✓ Sin entregas pendientes en Classroom.")
            y_cr += 16
        else:
            for asig in cr_act[:2]:
                painter.drawText(20, y_cr, f"• {asig['titulo'][:48]}...")
                y_cr += 16

        y_agenda = y_cr + 6
        painter.setPen(QColor(0, 230, 255))
        painter.setFont(QFont("Ubuntu", 8, QFont.Weight.Bold))
        painter.drawText(20, y_agenda, "PENDIENTES VIGENTES (LIRA / UNAM SPACE / SUMA):")
        painter.setPen(QColor(210, 230, 245))
        painter.setFont(QFont("Ubuntu", 8))
        y_item = y_agenda + 16
        for item in self.pendientes_top[:3]:
            recorte = item[:50] + "..." if len(item) > 50 else item
            painter.drawText(20, y_item, f"• {recorte}")
            y_item += 16

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos_local = event.position()

            if not self.modo_pantalla_completa and self.rect_btn_mute.contains(pos_local):
                self.alternar_modo_silencio()
                event.accept()
                return

            if self.rect_btn_full.contains(pos_local):
                self.alternar_pantalla_completa()
                event.accept()
                return

            if not self.modo_pantalla_completa and self.rect_btn_mini.contains(pos_local):
                self.modo_mini = not self.modo_mini
                self.aplicar_geometria_actual(conservar_pos=True)
                self.disparar_animacion_entrada()
                event.accept()
                return

            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            self._press_global_pos = event.globalPosition().toPoint()
            self._window_pos_at_press = self.pos()
            self._movio_en_arrastre = False

            if not self.modo_pantalla_completa and pos_local.y() <= 34:
                if self.windowHandle() is not None:
                    self.windowHandle().startSystemMove()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self.modo_pantalla_completa and self._press_global_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            delta = event.globalPosition().toPoint() - self._press_global_pos
            if delta.manhattanLength() > 5:
                self._movio_en_arrastre = True
                nueva_pos = self._window_pos_at_press + delta
                self.move(nueva_pos)
                self.posicion_guardada = nueva_pos
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        pos_local = event.position()

        if event.button() == Qt.MouseButton.LeftButton and not self._movio_en_arrastre:
            if self.rect_reactor.contains(pos_local):
                self.alternar_pantalla_completa()

        self._press_global_pos = None
        self._window_pos_at_press = None
        self._movio_en_arrastre = False
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = JarvisHologramHUD()
    hud.show()
    sys.exit(app.exec())
