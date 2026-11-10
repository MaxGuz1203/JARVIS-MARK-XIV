#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Etapa 4: HUD Visual Flotante Estilo Holograma (PySide6)
Renderiza anillos animados, estado del agente, telemetría y pendientes activos.
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import datetime
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import psutil
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

ARCHIVO_ESTADO_HUD = Path("/tmp/jarvis_hud_state.json")
ARCHIVO_AGENDA = Path.home() / "jarvis" / "agenda.json"


def escribir_estado_hud(estado: str, subtexto: str = "", visible: bool = True) -> None:
    """Función auxiliar llamada por jarvis_wake.py para actualizar el HUD en tiempo real."""
    datos = {
        "estado": estado,
        "subtexto": subtexto[:95] + "..." if len(subtexto) > 95 else subtexto,
        "visible": visible,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    try:
        ARCHIVO_ESTADO_HUD.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class JarvisHologramHUD(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. HUD")
        self.setFixedSize(360, 430)

        # Ventana sin bordes, translúcida y siempre encima
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Posicionar en la esquina superior derecha de la pantalla
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.move(pantalla.width() - self.width() - 25, 45)

        # Variables de animación y telemetría
        self.angulo_ext = 0.0
        self.angulo_int = 360.0
        self.pulso = 0.0
        self.estado_actual = "EN LÍNEA"
        self.subtexto = "Sistemas nominales. Esperando instrucciones."
        self.cpu_pct = 0
        self.ram_pct = 0
        self.gpu_temp = "--"
        self.bat_pct = 100
        self.pendientes_top = []
        self._drag_pos: QPoint | None = None

        # Timer de animación a 30 FPS (33 ms)
        self.timer_anim = QTimer(self)
        self.timer_anim.timeout.connect(self.actualizar_animacion)
        self.timer_anim.start(33)

        # Timer de telemetría y agenda cada 2 segundos
        self.timer_telemetria = QTimer(self)
        self.timer_telemetria.timeout.connect(self.actualizar_telemetria)
        self.timer_telemetria.start(2000)
        self.actualizar_telemetria()

    def obtener_color_estado(self) -> QColor:
        mapa = {
            "EN LÍNEA": QColor(0, 230, 255),      # Cian clásico J.A.R.V.I.S.
            "ESCUCHANDO": QColor(0, 255, 140),    # Verde neón activo
            "PROCESANDO": QColor(255, 185, 0),    # Ámbar cognitivo
            "HABLANDO": QColor(60, 160, 255),     # Azul eléctrico intenso
            "ALERTA": QColor(255, 65, 65),        # Rojo preventivo
        }
        return mapa.get(self.estado_actual, QColor(0, 230, 255))

    def actualizar_animacion(self) -> None:
        velocidad = 4.5 if self.estado_actual in ("PROCESANDO", "HABLANDO") else 1.8
        self.angulo_ext = (self.angulo_ext + velocidad) % 360
        self.angulo_int = (self.angulo_int - velocidad * 1.4) % 360
        self.pulso = (self.pulso + 0.15) % (2 * math.pi)

        if ARCHIVO_ESTADO_HUD.exists():
            try:
                datos = json.loads(ARCHIVO_ESTADO_HUD.read_text(encoding="utf-8"))
                self.estado_actual = datos.get("estado", "EN LÍNEA")
                self.subtexto = datos.get("subtexto", self.subtexto)
                visible = datos.get("visible", True)
                if not visible and self.isVisible():
                    self.hide()
                elif visible and not self.isVisible():
                    self.show()
            except Exception:
                pass

        self.update()

    def actualizar_telemetria(self) -> None:
        self.cpu_pct = round(psutil.cpu_percent())
        self.ram_pct = round(psutil.virtual_memory().percent)
        bat = psutil.sensors_battery()
        self.bat_pct = round(bat.percent) if bat else 100

        if shutil.which("nvidia-smi"):
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                self.gpu_temp = f"{out}°C" if out.isdigit() else "--"
            except Exception:
                self.gpu_temp = "--"

        if ARCHIVO_AGENDA.exists():
            try:
                ag = json.loads(ARCHIVO_AGENDA.read_text(encoding="utf-8"))
                activos = [p for p in ag.get("pendientes", []) if not p.get("completado", False)]
                self.pendientes_top = [f"[{p['categoria']}] {p['titulo']}" for p in activos[:3]]
            except Exception:
                pass

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_p = self.obtener_color_estado()

        # 1. Fondo translúcido estilo cristal oscuro con borde holográfico
        painter.setBrush(QColor(8, 15, 26, 210))
        pen_borde = QPen(QColor(color_p.red(), color_p.green(), color_p.blue(), 130), 1.5)
        painter.setPen(pen_borde)
        painter.drawRoundedRect(QRectF(5, 5, self.width() - 10, self.height() - 10), 16, 16)

        # 2. Dibujar Núcleo Arc Reactor (Centro superior)
        cx, cy = 75, 80
        radio_ext = 46
        radio_int = 32

        # Resplandor radial central
        escala_pulso = 1.0 + 0.12 * math.sin(self.pulso)
        grad = QRadialGradient(cx, cy, radio_int * escala_pulso)
        grad.setColorAt(0.0, QColor(color_p.red(), color_p.green(), color_p.blue(), 190))
        grad.setColorAt(0.6, QColor(color_p.red(), color_p.green(), color_p.blue(), 55))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(radio_int * escala_pulso), int(radio_int * escala_pulso))

        # Anillo exterior segmentado giratorio
        pen_ext = QPen(color_p, 3.0)
        painter.setPen(pen_ext)
        rect_ext = QRectF(cx - radio_ext, cy - radio_ext, radio_ext * 2, radio_ext * 2)
        for i in range(3):
            inicio = int((self.angulo_ext + i * 120) * 16)
            painter.drawArc(rect_ext, inicio, 75 * 16)

        # Anillo interior contrarrotatorio
        pen_int = QPen(QColor(color_p.red(), color_p.green(), color_p.blue(), 180), 2.0)
        painter.setPen(pen_int)
        rect_int = QRectF(cx - radio_int, cy - radio_int, radio_int * 2, radio_int * 2)
        for i in range(2):
            inicio = int((self.angulo_int + i * 180) * 16)
            painter.drawArc(rect_int, inicio, 110 * 16)

        # 3. Encabezado y Reloj Digital
        painter.setPen(color_p)
        painter.setFont(QFont("Ubuntu", 13, QFont.Weight.Bold))
        painter.drawText(140, 48, "J.A.R.V.I.S.  MARK IV")

        painter.setPen(QColor(200, 235, 255))
        painter.setFont(QFont("Ubuntu Mono", 10, QFont.Weight.Bold))
        ahora_str = datetime.datetime.now().strftime("%H:%M:%S  |  %d/%m/%Y")
        painter.drawText(140, 70, ahora_str)

        painter.setPen(color_p)
        painter.setFont(QFont("Ubuntu", 10, QFont.Weight.Bold))
        painter.drawText(140, 95, f"ESTADO: {self.estado_actual}")

        # 4. Subtexto / Última transmisión
        painter.setPen(QColor(175, 210, 230))
        painter.setFont(QFont("Ubuntu", 9))
        painter.drawText(QRectF(20, 140, 320, 38), Qt.TextFlag.TextWordWrap, f"» {self.subtexto}")

        # 5. Barras de Telemetría (CPU, RAM, Batería y GPU)
        y_base = 192
        metricas = [
            ("CPU", self.cpu_pct, f"{self.cpu_pct}%"),
            ("RAM", self.ram_pct, f"{self.ram_pct}%"),
            ("BAT", self.bat_pct, f"{self.bat_pct}%"),
        ]
        for etiqueta, valor, texto_val in metricas:
            painter.setPen(QColor(180, 220, 240))
            painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
            painter.drawText(20, y_base + 11, etiqueta)

            # Fondo de barra
            painter.setBrush(QColor(25, 45, 65, 180))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(60, y_base, 220, 12), 4, 4)

            # Relleno de barra
            ancho_val = max(4, int(2.2 * min(100, valor)))
            painter.setBrush(color_p)
            painter.drawRoundedRect(QRectF(60, y_base, ancho_val, 12), 4, 4)

            painter.setPen(QColor(220, 245, 255))
            painter.drawText(290, y_base + 11, texto_val)
            y_base += 24

        painter.setPen(color_p)
        painter.setFont(QFont("Ubuntu Mono", 9, QFont.Weight.Bold))
        painter.drawText(20, y_base + 12, f"GPU NVIDIA TEMP: {self.gpu_temp}")

        # 6. Panel de Orden del Día / Pendientes Críticos
        y_agenda = y_base + 36
        painter.setPen(QColor(0, 230, 255))
        painter.setFont(QFont("Ubuntu", 9, QFont.Weight.Bold))
        painter.drawText(20, y_agenda, "ORDEN DEL DÍA (PRIORIDADES):")

        painter.setPen(QColor(210, 230, 245))
        painter.setFont(QFont("Ubuntu", 8))
        y_item = y_agenda + 18
        for item in self.pendientes_top:
            recorte = item[:48] + "..." if len(item) > 48 else item
            painter.drawText(20, y_item, f"• {recorte}")
            y_item += 18

    # Permitir arrastrar el holograma con el mouse a cualquier parte del escritorio
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = JarvisHologramHUD()
    hud.show()
    sys.exit(app.exec())
