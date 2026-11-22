#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Motor de Modelado y Proyección 3D Holográfica Interactiva (Mark XIII - Nativo)
- Motor 3D Matricial con Z-Buffer propio en HTML5 Canvas (Cero dependencia de CDNs o WebGL frágil)
- Garantiza fondo oscuro holográfico, carga inmediata de paneles y rotación 360° con dedos/ratón
- Vista Explosiva, Rayos X (Wireframe), Corte Transversal, Vectores Magnéticos y Selección por Clic
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import datetime
import html
import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from jarvis_hud import escribir_estado_hud
from jarvis_memory import registrar_turno_conversacion

DIRECTORIO_BASE = Path.home() / "jarvis"
DIRECTORIO_MODELOS_3D = DIRECTORIO_BASE / "modelos_3d"
ARCHIVO_ENV = DIRECTORIO_BASE / ".env"


def _cargar_key() -> str:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if ARCHIVO_ENV.exists():
        for l in ARCHIVO_ENV.read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("GEMINI_API_KEY="):
                return l.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _resumen_wiki_3d(tema: str) -> str:
    try:
        url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(tema)}&utf8=&format=json&srlimit=2"
        req = urllib.request.Request(url, headers={"User-Agent": "Jarvis3DEngine/13.1"})
        with urllib.request.urlopen(req, timeout=3.5) as r:
            items = json.loads(r.read().decode("utf-8")).get("query", {}).get("search", [])
            textos = []
            for it in items:
                t = it.get("title", "")
                u2 = f"https://es.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(t)}"
                with urllib.request.urlopen(urllib.request.Request(u2, headers={"User-Agent": "Jarvis3DEngine/13.1"}), timeout=3.0) as r2:
                    ext = json.loads(r2.read().decode("utf-8")).get("extract", "")
                    if ext:
                        textos.append(f"{t}: {ext}")
            return " ".join(textos)
    except Exception:
        return ""


def obtener_catalogo_planos_base(tema_low: str) -> dict | None:
    if any(k in tema_low for k in ("jaula de ardilla", "inducción", "induccion", "motor electrico", "motor eléctrico", "asíncrono", "asincrono")):
        return {
            "preset": "SQUIRREL_CAGE_MOTOR",
            "titulo": "MOTOR DE INDUCCIÓN TRIFÁSICO TIPO JAULA DE ARDILLA",
            "subtitulo": "Simulación Electromagnética 3D // Estator Devanado, Rotor en Cortocircuito y Campo Giratorio Bs",
            "principio": (
                "Al alimentar el estator con un sistema trifásico equilibrado a frecuencia f, se establece un campo magnético "
                "giratorio Bs que rota a velocidad síncrona ns = 120·f / P. Este flujo corta las barras de aluminio/cobre del rotor, "
                "induciendo corrientes por la Ley de Faraday (e = -dΦ/dt). La interacción entre la corriente inducida y el campo "
                "produce el par electromagnético τ = k·(Bs × Br), haciendo girar el rotor a velocidad nr = ns·(1 - s)."
            ),
            "parametros": [
                ["Velocidad Síncrona (ns)", "1800 RPM (4 Polos, 60 Hz)"],
                ["Deslizamiento Nominal (s)", "3.5 % (s = (ns - nr)/ns)"],
                ["Potencia / Tensión", "5 HP | 220/440 V Trifásico"],
                ["Jaula del Rotor", "16 Barras Inclinadas (Skewed) + 2 Anillos"],
            ],
            "partes": [
                {
                    "id": "carcasa_estator",
                    "nombre": "1. Carcasa Aletada y Núcleo del Estator",
                    "funcion": "Soporte mecánico exterior con aletas de disipación térmica y paquete de chapas de acero al silicio ranuradas que alojan el devanado trifásico.",
                    "caracteristicas": "Acero laminado en frío (0.35 mm) para minimizar pérdidas por corrientes parásitas de Foucault e histéresis.",
                },
                {
                    "id": "devanado_trifasico",
                    "nombre": "2. Devanado Estatórico Trifásico (Fases U, V, W)",
                    "funcion": "Bobinas desfasadas 120° eléctricos en el espacio que producen la fuerza magnetomotriz resultante y el campo magnético rotatorio de amplitud constante.",
                    "caracteristicas": "Cobre electrolítico esmaltado clase H (180 °C), distribuido en las ranuras del estator.",
                },
                {
                    "id": "barras_jaula",
                    "nombre": "3. Barras Conductoras de la Jaula de Ardilla",
                    "funcion": "Conductores axiales alojados en el rotor donde se inducen las corrientes rotóricas proporcionales al deslizamiento s.",
                    "caracteristicas": "Barras de cobre/aluminio con inclinación axial (skew) para eliminar armónicos de ranura y par de enganche.",
                },
                {
                    "id": "anillos_corto",
                    "nombre": "4. Anillos de Cortocircuito (End Rings)",
                    "funcion": "Unen eléctricamente todas las barras conductoras en ambos extremos del rotor, cerrando el circuito sin necesidad de escobillas.",
                    "caracteristicas": "Anillos frontales y posteriores de baja resistencia con aletas disipadoras.",
                },
                {
                    "id": "nucleo_rotor",
                    "nombre": "5. Núcleo Ferromagnético Laminado del Rotor",
                    "funcion": "Conduce el flujo magnético a través del entrehierro con mínima reluctancia magnética.",
                    "caracteristicas": "Entrehierro radial calibrado (0.4 a 0.8 mm) para maximizar el factor de potencia.",
                },
                {
                    "id": "eje_motriz",
                    "nombre": "6. Eje Motriz (Shaft) y Rodamientos",
                    "funcion": "Transmite el par mecánico desarrollado (τ_ind = P_conv / ω_r) hacia la carga mecánica acoplada.",
                    "caracteristicas": "Acero de alta resistencia AISI 4140 rectificado.",
                },
                {
                    "id": "campo_giratorio",
                    "nombre": "7. Campo Magnético Giratorio (Vectores Bs)",
                    "funcion": "Flujo magnético rotatorio en el entrehierro que gira a ω_s = 2π·ns/60 rad/s adelantando al rotor.",
                    "caracteristicas": "Densidad de flujo pico en el entrehierro B_max ≈ 0.75 a 0.90 Tesla.",
                },
            ],
        }

    if "transformador" in tema_low:
        return {
            "preset": "TRANSFORMER_3D",
            "titulo": "TRANSFORMADOR ELÉCTRICO DE POTENCIA Y FLUJO MUTUO",
            "subtitulo": "Núcleo Ferromagnético Laminado, Devanados Primario/Secundario y Líneas de Flujo Φm",
            "principio": (
                "Opera por inducción electromagnética mutua entre dos o más devanados acoplados magnéticamente a través de un núcleo "
                "de alta permeabilidad (µr >> 1). La tensión alterna V1 crea un flujo alterno Φ = Φmax·sen(ωt) que enlaza ambos devanados, "
                "cumpliendo la relación de transformación ideal V1 / V2 = N1 / N2 = I2 / I1."
            ),
            "parametros": [
                ["Relación de Transformación (a)", "N1 / N2 = 2.0 (Reductor/Elevador)"],
                ["Frecuencia de Operación", "60 Hz | Flujo Magnético Senoidal"],
                ["Eficiencia Nominal (η)", "98.4 % a plena carga"],
                ["Núcleo Magnético", "Acero al Silicio de Grano Orientado (CRGO)"],
            ],
            "partes": [
                {"id": "nucleo_fe", "nombre": "1. Núcleo Ferromagnético Laminado", "funcion": "Canaliza el flujo magnético mutuo Φm con reluctancia mínima entre primario y secundario.", "caracteristicas": "Chapas aisladas para reducir pérdidas en el hierro (P_Fe = P_h + P_f)."},
                {"id": "bobina_primaria", "nombre": "2. Devanado Primario (Alta Tensión - N1)", "funcion": "Recibe la energía eléctrica de la red y establece la fuerza magnetomotriz FMM = N1·I1.", "caracteristicas": "Bobinado concéntrico de cobre electrolítico."},
                {"id": "bobina_secundaria", "nombre": "3. Devanado Secundario (Baja Tensión - N2)", "funcion": "Entrega potencia eléctrica inducida por la variación temporal del flujo mutuo (E2 = 4.44·f·N2·Φmax).", "caracteristicas": "Mayor sección transversal para conducir la corriente secundaria I2."},
                {"id": "aisladores_bushings", "nombre": "4. Boquillas Pasatapas (Bushings AT/BT)", "funcion": "Aíslan dieléctricamente las terminales de conexión de alta y baja tensión.", "caracteristicas": "Porcelana electrotécnica de alta rigidez."},
                {"id": "flujo_magnetico", "nombre": "5. Flujo Magnético Mutuo (Φm)", "funcion": "Trayectoria cerrada de inducción magnética B dentro de las columnas y yugos.", "caracteristicas": "Densidad de operación B ≈ 1.5 Tesla."},
            ],
        }

    if any(k in tema_low for k in ("campo magnético", "campo magnetico", "solenoide", "campo eléctrico", "campo electrico", "electromagn", "faraday", "maxwell")):
        return {
            "preset": "EM_FIELD_SOLENOID",
            "titulo": "SOLENOIDE 3D Y DISTRIBUCIÓN DE CAMPO ELECTROMAGNÉTICO",
            "subtitulo": "Ley de Ampère-Maxwell // Líneas de Inducción Magnética B, Vectores de Campo y Espiras",
            "principio": (
                "Por la Ley de Ampère (∮ B·dl = µ0·I_enc), una corriente eléctrica I que circula por un solenoide helicoidal de N espiras "
                "y longitud L genera en su interior un campo magnético uniforme y axial B = µ0·(N/L)·I, mientras que en el exterior las "
                "líneas de campo se cierran de polo Norte a polo Sur."
            ),
            "parametros": [
                ["Campo Interior (B_int)", "B = µ0 · n · I  [Tesla]"],
                ["Permeabilidad (µ0)", "4π × 10⁻⁷ T·m/A"],
                ["Inductancia (L)", "L = µ0 · N² · A / l  [Henrios]"],
                ["Densidad de Energía (u_B)", "u = B² / (2·µ0)  [J/m³]"],
            ],
            "partes": [
                {"id": "bobina_helice", "nombre": "1. Devanado Helicoidal del Solenoide", "funcion": "Conduce la corriente de excitación I generando un campo magnético aditivo en el eje central.", "caracteristicas": "Geometría cilíndrica de N espiras."},
                {"id": "lineas_internas", "nombre": "2. Núcleo de Flujo Axial Uniforme (Campo B)", "funcion": "Región central donde los vectores de campo magnético son paralelos e intensos.", "caracteristicas": "Dirección determinada por la regla de la mano derecha."},
                {"id": "lineas_dipolo", "nombre": "3. Lóbulos Exteriores de Campo Dipolar", "funcion": "Líneas cerradas de flujo magnético que emergen por el polo Norte y reingresan por el Sur (∇·B = 0).", "caracteristicas": "Cumple la Ley de Gauss para el magnetismo."},
                {"id": "anillos_equipotenciales", "nombre": "4. Anillos de Potencial Magnético", "funcion": "Representan la simetría azimutal del campo alrededor del eje de conducción.", "caracteristicas": "Visualización vectorial dinámica."},
            ],
        }

    if any(k in tema_low for k in ("rover", "unam space", "robot", "vehículo", "vehiculo")):
        return {
            "preset": "ROVER_6WD",
            "titulo": "ROVER DE EXPLORACIÓN ESPACIAL 6WD — ARQUITECTURA UNAM SPACE",
            "subtitulo": "Suspensión Rocker-Bogie, Tracción Hexa-Motor con Puentes H BTS7960, Mástil Óptico y Brazo 6-DOF",
            "principio": (
                "El sistema utiliza tracción independiente en sus 6 ruedas (6WD) controlada por PWM a través de puentes H de alta "
                "corriente BTS7960 (43 A) y telemetría inalámbrica ESP32/ROS 2, manteniendo estabilidad sobre terreno irregular."
            ),
            "parametros": [
                ["Tracción y Potencia", "6 Motores DC + 6 Drivers BTS7960"],
                ["Control y Enlace", "ESP32U + Arduino Mega + ROS 2 Nav2"],
                ["Manipulador", "Brazo Robótico 6-DOF (PCA9685 PWM)"],
                ["Alimentación", "Batería LiPo Alta Descarga"],
            ],
            "partes": [
                {"id": "chasis_central", "nombre": "1. Chasis Estructural y Bahía de Potencia", "funcion": "Aloja las placas PCB de distribución, los puentes H BTS7960 y la computadora de misión.", "caracteristicas": "Aleación ligera de aluminio y polímero estructural."},
                {"id": "ruedas_6wd", "nombre": "2. Conjunto de 6 Ruedas Motorizadas", "funcion": "Proporcionan tracción diferencial todo terreno.", "caracteristicas": "Banda de rodadura con tacos para terreno rocoso."},
                {"id": "suspension_rocker", "nombre": "3. Eslabones de Suspensión Rocker-Bogie", "funcion": "Reparten equitativamente la carga sobre los 6 puntos de apoyo.", "caracteristicas": "Articulaciones rotacionales cinemáticas."},
                {"id": "mastil_camara", "nombre": "4. Mástil Estereoscópico y Navegación Visual", "funcion": "Soporta las cámaras de localización visual y generación de mapas de costos 2D.", "caracteristicas": "Cabezal pan-tilt."},
                {"id": "brazo_robotico", "nombre": "5. Brazo Robótico Articulado 6-DOF", "funcion": "Recolección de muestras y accionamiento de controles.", "caracteristicas": "Servomotores MG995/MG90S controlados por PCA9685."},
            ],
        }

    return None


def generar_plano_3d_universal_con_gemini(tema: str, contexto_wiki: str) -> dict:
    api_key = _cargar_key()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                f"Actúa como el motor CAD 3D holográfico de J.A.R.V.I.S. para el ingeniero Max.\n"
                f"Diseña un modelo 3D interactivo detallado de: '{tema}'. Contexto: {contexto_wiki[:800]}\n"
                f"Devuelve ÚNICAMENTE un JSON válido (sin markdown) con esta estructura:\n"
                f'{{"preset": "CUSTOM_GEMINI_3D", "titulo": "TÍTULO EN MAYÚSCULAS", "subtitulo": "Subtítulo técnico", '
                f'"principio": "Explicación física de 3 oraciones", '
                f'"parametros": [["Parámetro 1", "Valor 1"], ["Parámetro 2", "Valor 2"], ["Parámetro 3", "Valor 3"], ["Parámetro 4", "Valor 4"]], '
                f'"partes": [{{"id": "p1", "nombre": "1. Nombre de Parte", "funcion": "Qué hace", "caracteristicas": "Especificaciones", '
                f'"geom": "cylinder|box|sphere|torus|cone", "args": [1.0, 1.0, 2.0], "pos": [0.0, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], '
                f'"color": "#00e5ff", "anim": "rotor|field|none"}}]}} '
                f"Incluye de 5 a 7 partes bien distribuidas en coordenadas [-2.2 a 2.2]."
            )
            for mod in ("models/gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash"):
                try:
                    res = client.models.generate_content(model=mod, contents=prompt)
                    m = re.search(r"\{.*\}", (res.text or ""), re.DOTALL)
                    if m:
                        datos = json.loads(m.group(0))
                        if "partes" in datos and len(datos["partes"]) >= 2:
                            datos["preset"] = "CUSTOM_GEMINI_3D"
                            return datos
                except Exception:
                    continue
        except Exception:
            pass

    return {
        "preset": "CUSTOM_GEMINI_3D",
        "titulo": f"MODELO HOLOGRÁFICO 3D // {tema.upper()}",
        "subtitulo": "Reconstrucción Paramétrica Interactiva Multi-Capas",
        "principio": contexto_wiki[:420] if contexto_wiki else f"Modelo tridimensional interactivo de {tema} generado por los sistemas holográficos de J.A.R.V.I.S.",
        "parametros": [
            ["Sistema Analizado", tema.title()],
            ["Interacción", "Rotación 360° + Vista Explosiva + Rayos X"],
            ["Motor Gráfico", "J.A.R.V.I.S. Matrix 3D Z-Buffer"],
            ["Inspección", "Selección Táctil y por Clic en Piezas"],
        ],
        "partes": [
            {"id": "nucleo", "nombre": f"1. Núcleo Principal de {tema.title()}", "funcion": "Estructura central portadora del flujo de energía y estabilidad mecánica.", "caracteristicas": "Geometría primaria de alta densidad.", "geom": "cylinder", "args": [1.0, 1.0, 2.4], "pos": [0, 0, 0], "rot": [0, 0, 1.57], "color": "#00e5ff", "anim": "rotor"},
            {"id": "anillo", "nombre": "2. Anillo Concentrador / Estator Exterior", "funcion": "Envuelve al núcleo proporcionando confinamiento de campo y soporte.", "caracteristicas": "Aleación conductora / magnética.", "geom": "torus", "args": [1.65, 0.25], "pos": [0, 0, 0], "rot": [0, 1.57, 0], "color": "#ffca28", "anim": "none"},
            {"id": "etapa_in", "nombre": "3. Etapa Frontal de Excitación", "funcion": "Recibe la señal o energía de entrada y regula la transferencia hacia el núcleo.", "caracteristicas": "Acoplamiento axial directo.", "geom": "cylinder", "args": [0.65, 0.85, 1.1], "pos": [-1.7, 0, 0], "rot": [0, 0, 1.57], "color": "#00ffaa", "anim": "rotor"},
            {"id": "etapa_out", "nombre": "4. Etapa Posterior de Potencia / Salida", "funcion": "Entrega la respuesta procesada o el par mecánico resultante.", "caracteristicas": "Alta eficiencia de conversión.", "geom": "cylinder", "args": [0.4, 0.4, 2.0], "pos": [1.7, 0, 0], "rot": [0, 0, 1.57], "color": "#70d6ff", "anim": "rotor"},
            {"id": "envolvente", "nombre": "5. Carcasa / Campo Envolvente", "funcion": "Protección térmica y blindaje electromagnético del conjunto.", "caracteristicas": "Visualizable en modo Rayos X.", "geom": "sphere", "args": [2.15], "pos": [0, 0, 0], "rot": [0, 0, 0], "color": "#0096c7", "anim": "field"},
        ],
    }


def construir_html_visor_3d_stark(especificacion: dict) -> Path:
    DIRECTORIO_MODELOS_3D.mkdir(parents=True, exist_ok=True)
    spec_json = json.dumps(especificacion, ensure_ascii=False)
    ruta_tmp = Path("/tmp/jarvis_hologram_3d.html")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", especificacion.get("titulo", "modelo").lower()).strip("_")[:35]
    ruta_copia = DIRECTORIO_MODELOS_3D / f"holograma_3d_{slug}.html"

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>J.A.R.V.I.S. MARK XIII // HOLOGRAMA 3D: {html.escape(especificacion.get('titulo', ''))}</title>
<style>
  * {{ box-sizing: border-box; user-select: none; }}

  @keyframes starkHologramIn {{
    0% {{ opacity: 0; transform: scale(0.84) perspective(900px) rotateX(12deg); filter: brightness(2.5) blur(6px); }}
    60% {{ opacity: 0.95; transform: scale(1.01) perspective(900px) rotateX(0deg); filter: brightness(1.4) blur(0px); }}
    100% {{ opacity: 1; transform: scale(1.0); filter: brightness(1.0); }}
  }}
  @keyframes starkHologramOut {{
    0% {{ opacity: 1; transform: scale(1.0); filter: brightness(1.2); }}
    50% {{ opacity: 0.7; transform: scale(0.92, 0.04); filter: brightness(3.0) drop-shadow(0 0 30px #00e5ff); }}
    100% {{ opacity: 0; transform: scale(0.0, 0.0); }}
  }}
  body {{ animation: starkHologramIn 0.85s cubic-bezier(0.16, 1, 0.3, 1) forwards; }}
  body.closing-hologram {{ animation: starkHologramOut 0.55s ease-in forwards; }}

  html, body {{
    width: 100vw; height: 100vh; margin: 0; padding: 0; overflow: hidden;
    background-color: #030914 !important;
    background-image:
      radial-gradient(circle at 50% 50%, rgba(0, 180, 255, 0.16) 0%, rgba(2, 6, 14, 0.98) 75%),
      linear-gradient(rgba(0, 229, 255, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0, 229, 255, 0.05) 1px, transparent 1px) !important;
    background-size: 100% 100%, 36px 36px, 36px 36px !important;
    color: #dff6ff; font-family: 'Ubuntu', 'Segoe UI', sans-serif;
  }}
  #hologram-canvas {{
    position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1;
    cursor: grab; display: block;
  }}
  #hologram-canvas:active {{ cursor: grabbing; }}
  .hud-overlay {{ position: absolute; top: 0; left: 0; z-index: 10; pointer-events: none; width: 100vw; height: 100vh; }}
  .interactive {{ pointer-events: auto; }}
  .top-header {{
    position: absolute; top: 14px; left: 20px; right: 20px;
    display: flex; justify-content: space-between; align-items: center;
    background: rgba(5, 16, 32, 0.90); border: 1.5px solid #00e5ff;
    border-radius: 12px; padding: 11px 22px; box-shadow: 0 0 25px rgba(0, 229, 255, 0.25);
  }}
  .title-block h1 {{ margin: 0; font-size: 18.5px; color: #00e5ff; letter-spacing: 1.1px; text-shadow: 0 0 10px rgba(0,229,255,0.4); }}
  .title-block p {{ margin: 3px 0 0 0; font-size: 12px; color: #ffca28; font-family: 'Ubuntu Mono', monospace; }}
  .left-panel {{
    position: absolute; top: 90px; left: 20px; width: 325px; max-height: calc(100vh - 175px);
    background: rgba(5, 15, 28, 0.90); border: 1.5px solid rgba(0, 229, 255, 0.65);
    border-radius: 14px; padding: 15px; overflow-y: auto; box-shadow: 0 0 25px rgba(0,0,0,0.7);
  }}
  .right-panel {{
    position: absolute; top: 90px; right: 20px; width: 355px; max-height: calc(100vh - 175px);
    background: rgba(5, 15, 28, 0.90); border: 1.5px solid rgba(0, 229, 255, 0.65);
    border-radius: 14px; padding: 16px; overflow-y: auto; box-shadow: 0 0 25px rgba(0,0,0,0.7);
  }}
  .bottom-bar {{
    position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%);
    background: rgba(5, 16, 32, 0.94); border: 1.5px solid #00e5ff; border-radius: 14px;
    padding: 10px 18px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
    box-shadow: 0 0 30px rgba(0, 229, 255, 0.3);
  }}
  .panel-title {{
    color: #ffca28; font-family: 'Ubuntu Mono', monospace; font-size: 12px;
    font-weight: bold; border-bottom: 1px solid rgba(0,229,255,0.35); padding-bottom: 5px; margin-bottom: 9px;
  }}
  .part-btn {{
    display: block; width: 100%; text-align: left; background: rgba(0, 229, 255, 0.09);
    color: #d8f3ff; border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 7px;
    padding: 7px 10px; margin-bottom: 6px; font-size: 12px; cursor: pointer; transition: 0.18s;
  }}
  .part-btn:hover, .part-btn.active {{
    background: rgba(255, 202, 40, 0.24); border-color: #ffca28; color: #fff; font-weight: bold;
    box-shadow: 0 0 12px rgba(255, 202, 40, 0.35);
  }}
  .ctrl-btn {{
    background: rgba(0, 150, 210, 0.22); color: #00e5ff; border: 1px solid #00e5ff;
    border-radius: 8px; padding: 7px 12px; font-family: 'Ubuntu Mono', monospace;
    font-size: 11.5px; font-weight: bold; cursor: pointer; transition: 0.2s;
  }}
  .ctrl-btn:hover, .ctrl-btn.active {{
    background: rgba(255, 202, 40, 0.26); color: #ffca28; border-color: #ffca28;
  }}
  .slider-group {{ display: flex; align-items: center; gap: 7px; font-family: 'Ubuntu Mono', monospace; font-size: 11px; color: #ffca28; }}
  input[type=range] {{ accent-color: #00e5ff; cursor: pointer; width: 95px; }}
  .param-row {{ display: flex; justify-content: space-between; font-size: 11.5px; padding: 5px 0; border-bottom: 1px dashed rgba(0,229,255,0.2); gap: 8px; }}
  .param-row span:first-child {{ color: #8ecae6; }}
  .param-row span:last-child {{ color: #fff; font-weight: bold; font-family: 'Ubuntu Mono', monospace; text-align: right; }}
  .info-box {{ font-size: 13px; line-height: 1.52; color: #e2f6ff; margin-bottom: 12px; text-align: justify; }}
  .highlight-part {{ background: rgba(0, 229, 255, 0.10); border-left: 4px solid #ffca28; padding: 10px 12px; border-radius: 6px; margin-top: 8px; }}
</style>
</head>
<body>
<canvas id="hologram-canvas"></canvas>

<div class="hud-overlay">
  <div class="top-header interactive">
    <div class="title-block">
      <h1 id="hud-titulo">J.A.R.V.I.S. MARK XIII // LABORATORIO HOLOGRÁFICO 3D</h1>
      <p id="hud-subtitulo">Arrastre con sus dedos o ratón para girar 360° | Rueda/Pellizco para Zoom | Clic en una pieza para inspeccionar</p>
    </div>
    <div style="display:flex;gap:10px;"><button class="ctrl-btn" onclick="hablarExplicacionActual()">🔊 ESCUCHAR EXPLICACIÓN</button><button class="ctrl-btn" style="border-color:#ff4d6d;color:#ff758f;" onclick="cerrarHologramaStark()">✖ CERRAR HOLOGRAMA</button></div>
  </div>

  <div class="left-panel interactive">
    <div class="panel-title">🔩 COMPONENTES DEL MODELO (CLIC PARA VER)</div>
    <div id="lista-partes"></div>
    <div class="panel-title" style="margin-top:12px;">⚡ PARÁMETROS DE INGENIERÍA</div>
    <div id="lista-parametros"></div>
  </div>

  <div class="right-panel interactive">
    <div class="panel-title">🧠 ANÁLISIS FÍSICO Y FUNCIONAMIENTO</div>
    <div id="texto-principio" class="info-box"></div>
    <div class="panel-title">🔍 INSPECCIÓN DE PIEZA SELECCIONADA</div>
    <div id="detalle-pieza" class="highlight-part">
      <strong style="color:#ffca28; font-size:13.5px;" id="pieza-nombre">Seleccione una pieza</strong>
      <p id="pieza-funcion" style="margin:6px 0; font-size:12.5px; line-height:1.45;"></p>
      <div id="pieza-caract" style="font-size:11.5px; color:#8ecae6; font-family:'Ubuntu Mono',monospace;"></div>
    </div>
  </div>

  <div class="bottom-bar interactive">
    <button id="btn-explode" class="ctrl-btn" onclick="toggleExplode()">💥 VISTA EXPLOSIVA</button>
    <div class="slider-group">
      <span>DESENSAMBLAR:</span>
      <input id="slider-explode" type="range" min="0" max="100" value="0" oninput="ajustarExplosion(this.value)">
    </div>
    <button id="btn-cutaway" class="ctrl-btn active" onclick="toggleCutaway()">🔪 CORTE INTERNO</button>
    <button id="btn-xray" class="ctrl-btn" onclick="toggleXRay()">🦴 RAYOS X (WIREFRAME)</button>
    <button id="btn-field" class="ctrl-btn active" onclick="toggleCampos()">🧲 FLUJO / CAMPOS 3D</button>
    <div class="slider-group">
      <span>VELOCIDAD / RPM:</span>
      <input id="slider-speed" type="range" min="0" max="250" value="100" oninput="ajustarVelocidad(this.value)">
    </div>
    <button class="ctrl-btn" onclick="resetCamara()">🎯 CENTRAR VISTA</button>
  </div>
</div>

<script>
const SPEC = {spec_json};

// =========================================================================
// 1. POBLAR PANELES Y BOTONES DE INMEDIATO (ANTES DEL RENDERIZADO 3D)
// =========================================================================
document.getElementById('hud-titulo').innerText = SPEC.titulo || 'MODELO HOLOGRÁFICO 3D';
document.getElementById('hud-subtitulo').innerText = SPEC.subtitulo || '';
document.getElementById('texto-principio').innerText = SPEC.principio || '';

const contParams = document.getElementById('lista-parametros');
(SPEC.parametros || []).forEach(([k, v]) => {{
  const d = document.createElement('div');
  d.className = 'param-row';
  d.innerHTML = `<span>${{k}}</span><span>${{v}}</span>`;
  contParams.appendChild(d);
}});

let piezaSeleccionadaId = 'ALL';
let piezaActualTexto = SPEC.principio || '';

const contPartes = document.getElementById('lista-partes');
const btnTodas = document.createElement('button');
btnTodas.className = 'part-btn active';
btnTodas.id = 'btn-part-ALL';
btnTodas.innerText = '0. Ver Ensamble Completo';
btnTodas.onclick = () => seleccionarPieza('ALL');
contPartes.appendChild(btnTodas);

(SPEC.partes || []).forEach((p) => {{
  const btn = document.createElement('button');
  btn.className = 'part-btn';
  btn.id = 'btn-part-' + p.id;
  btn.innerText = p.nombre;
  btn.onclick = () => seleccionarPieza(p.id);
  contPartes.appendChild(btn);
}});

function seleccionarPieza(partId) {{
  piezaSeleccionadaId = partId;
  document.querySelectorAll('.part-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('btn-part-' + partId);
  if (btn) btn.classList.add('active');

  if (partId === 'ALL') {{
    const p0 = (SPEC.partes && SPEC.partes[0]) ? SPEC.partes[0] : null;
    document.getElementById('pieza-nombre').innerText = 'Ensamble Completo // ' + (SPEC.titulo || '');
    document.getElementById('pieza-funcion').innerText = 'Toque cualquier componente en la lista izquierda o directamente sobre el holograma 3D para aislarlo e inspeccionar su función.';
    document.getElementById('pieza-caract').innerText = p0 ? ('Componente #1: ' + p0.nombre) : '';
    piezaActualTexto = SPEC.principio;
    return;
  }}

  const info = (SPEC.partes || []).find(x => x.id === partId);
  if (!info) return;
  document.getElementById('pieza-nombre').innerText = info.nombre;
  document.getElementById('pieza-funcion').innerText = info.funcion;
  document.getElementById('pieza-caract').innerText = info.caracteristicas || '';
  piezaActualTexto = `${{info.nombre}}. ${{info.funcion}} ${{info.caracteristicas || ''}}`;
}}

seleccionarPieza('ALL');

// =========================================================================
// 2. MOTOR 3D MATRICIAL Z-BUFFER NATIVO EN HTML5 CANVAS (CERO FALLOS)
// =========================================================================
const canvas = document.getElementById('hologram-canvas');
const ctx = canvas.getContext('2d');

let W = window.innerWidth;
let H = window.innerHeight;
function resizeCanvas() {{
  W = window.innerWidth;
  H = window.innerHeight;
  canvas.width = W;
  canvas.height = H;
}}
resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// Estado de Cámara e Interacción (Dedos / Touchpad / Ratón)
let camRotX = 0.38;
let camRotY = -0.62;
let camZoom = 1.05;
let camPanX = 0;
let camPanY = 0;

let isDragging = false;
let isPanning = false;
let lastX = 0, lastY = 0;
let dragDist = 0;

let factorExplosion = 0.0;
let introEnsamble = 1.0; // Inicia desensamblado y se materializa hacia 0.0
let modoExplode = false;
let modoCutaway = true;
let modoXRay = false;
let mostrarCampos = true;
let factorVelocidad = 1.0;

canvas.addEventListener('pointerdown', (e) => {{
  isDragging = true;
  isPanning = (e.button === 2 || e.shiftKey);
  lastX = e.clientX;
  lastY = e.clientY;
  dragDist = 0;
  canvas.setPointerCapture(e.pointerId);
}});

canvas.addEventListener('pointermove', (e) => {{
  if (!isDragging) return;
  const dx = e.clientX - lastX;
  const dy = e.clientY - lastY;
  dragDist += Math.abs(dx) + Math.abs(dy);
  lastX = e.clientX;
  lastY = e.clientY;
  if (isPanning) {{
    camPanX += dx;
    camPanY += dy;
  }} else {{
    camRotY += dx * 0.0085;
    camRotX = Math.max(-1.45, Math.min(1.45, camRotX + dy * 0.0085));
  }}
}});

canvas.addEventListener('pointerup', (e) => {{
  isDragging = false;
  if (dragDist < 6) {{
    detectarClicEnPieza3D(e.clientX, e.clientY);
  }}
}});

canvas.addEventListener('contextmenu', e => e.preventDefault());

canvas.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.09 : 0.92;
  camZoom = Math.max(0.4, Math.min(3.2, camZoom * factor));
}}, {{ passive: false }});

// Constructores de Geometría 3D Poligonal (Caras + Normales + Vectores de Explosión)
const carasEscena = [];
const particulasCampo = [];

function hexToRgb(hex) {{
  const clean = hex.replace('#', '');
  const num = parseInt(clean, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}}

function agregarCara(verts, colorHex, partId, expVec, opacidad = 0.85, grupoAnim = 'static', esCorte = false) {{
  carasEscena.push({{
    verts: verts, // Array de [x,y,z]
    rgb: hexToRgb(colorHex),
    partId: partId,
    exp: expVec || [0, 0, 0],
    alpha: opacidad,
    anim: grupoAnim,
    cutaway: esCorte
  }});
}}

function agregarCilindro3D(opts) {{
  const {{
    r1 = 1, r2 = 1, len = 2, segs = 24,
    cx = 0, cy = 0, cz = 0, eje = 'x',
    color = '#00e5ff', partId = 'p', exp = [0,0,0],
    alpha = 0.85, anim = 'static', angMax = Math.PI * 2, skew = 0, tapar = true
  }} = opts;

  for (let i = 0; i < segs; i++) {{
    const a1 = (i / segs) * angMax;
    const a2 = ((i + 1) / segs) * angMax;
    const c1 = Math.cos(a1), s1 = Math.sin(a1);
    const c2 = Math.cos(a2), s2 = Math.sin(a2);
    const c1s = Math.cos(a1 + skew), s1s = Math.sin(a1 + skew);
    const c2s = Math.cos(a2 + skew), s2s = Math.sin(a2 + skew);
    const h = len / 2;

    let p1, p2, p3, p4;
    if (eje === 'x') {{
      p1 = [cx - h, cy + c1 * r1, cz + s1 * r1];
      p2 = [cx - h, cy + c2 * r1, cz + s2 * r1];
      p3 = [cx + h, cy + c2s * r2, cz + s2s * r2];
      p4 = [cx + h, cy + c1s * r2, cz + s1s * r2];
    }} else if (eje === 'y') {{
      p1 = [cx + c1 * r1, cy - h, cz + s1 * r1];
      p2 = [cx + c2 * r1, cy - h, cz + s2 * r1];
      p3 = [cx + c2s * r2, cy + h, cz + s2s * r2];
      p4 = [cx + c1s * r2, cy + h, cz + s1s * r2];
    }} else {{
      p1 = [cx + c1 * r1, cy + s1 * r1, cz - h];
      p2 = [cx + c2 * r1, cy + s2 * r1, cz - h];
      p3 = [cx + c2s * r2, cy + s2s * r2, cz + h];
      p4 = [cx + c1s * r2, cy + s1s * r2, cz + h];
    }}
    const esZonaCorte = (angMax < Math.PI * 2) ? false : (i > segs * 0.62 && i < segs * 0.95);
    agregarCara([p1, p2, p3, p4], color, partId, exp, alpha, anim, opts.permitirCorte && esZonaCorte);
  }}
}}

function agregarToro3D(opts) {{
  const {{
    R = 1.4, r = 0.16, segsR = 24, segsr = 10,
    cx = 0, cy = 0, cz = 0, eje = 'x',
    color = '#ffca28', partId = 'p', exp = [0,0,0], alpha = 0.9, anim = 'static'
  }} = opts;

  for (let i = 0; i < segsR; i++) {{
    const u1 = (i / segsR) * Math.PI * 2;
    const u2 = ((i + 1) / segsR) * Math.PI * 2;
    for (let j = 0; j < segsr; j++) {{
      const v1 = (j / segsr) * Math.PI * 2;
      const v2 = ((j + 1) / segsr) * Math.PI * 2;
      const pts = [[u1,v1], [u2,v1], [u2,v2], [u1,v2]].map(([u, v]) => {{
        const rad = R + r * Math.cos(v);
        const px = r * Math.sin(v);
        const py = rad * Math.cos(u);
        const pz = rad * Math.sin(u);
        if (eje === 'x') return [cx + px, cy + py, cz + pz];
        if (eje === 'y') return [cx + py, cy + px, cz + pz];
        return [cx + py, cy + pz, cz + px];
      }});
      agregarCara(pts, color, partId, exp, alpha, anim, false);
    }}
  }}
}}

function agregarCaja3D(opts) {{
  const {{
    wx = 1, wy = 1, wz = 1, cx = 0, cy = 0, cz = 0,
    color = '#00b4d8', partId = 'p', exp = [0,0,0], alpha = 0.85, anim = 'static'
  }} = opts;
  const hx = wx/2, hy = wy/2, hz = wz/2;
  const v = [
    [cx-hx, cy-hy, cz-hz], [cx+hx, cy-hy, cz-hz], [cx+hx, cy+hy, cz-hz], [cx-hx, cy+hy, cz-hz],
    [cx-hx, cy-hy, cz+hz], [cx+hx, cy-hy, cz+hz], [cx+hx, cy+hy, cz+hz], [cx-hx, cy+hy, cz+hz]
  ];
  const faces = [[0,1,2,3], [4,5,6,7], [0,1,5,4], [2,3,7,6], [0,3,7,4], [1,2,6,5]];
  faces.forEach(f => agregarCara(f.map(idx => v[idx]), color, partId, exp, alpha, anim, false));
}}

// =========================================================================
// 3. ENSAMBLAJE DE LOS MODELOS 3D SEGÚN EL PRESET
// =========================================================================
if (SPEC.preset === 'SQUIRREL_CAGE_MOTOR') {{
  // 1. Carcasa Aletada del Estator (con ventana de corte para ver el rotor interior)
  agregarCilindro3D({{
    r1: 2.15, r2: 2.15, len: 3.3, segs: 28, cx: 0, cy: 0, cz: 0, eje: 'x',
    color: '#0077b6', partId: 'carcasa_estator', exp: [0, 2.3, 0], alpha: 0.48, permitirCorte: true
  }});
  for (let i = 0; i < 12; i++) {{
    if (i >= 8 && i <= 10) continue; // Dejar ventana frontal de inspección
    const ang = (i / 12) * Math.PI * 2;
    const ay = Math.cos(ang) * 2.25;
    const az = Math.sin(ang) * 2.25;
    agregarCaja3D({{
      wx: 3.1, wy: 0.12, wz: 0.18, cx: 0, cy: ay, cz: az,
      color: '#00b4d8', partId: 'carcasa_estator', exp: [0, Math.cos(ang)*2.2, Math.sin(ang)*2.2], alpha: 0.65
    }});
  }}

  // 2. Devanado Estatórico Trifásico (Cabezas de bobina Fases U, V, W)
  const colFases = ['#ff9f1c', '#ef233c', '#2ec4b6'];
  for (let i = 0; i < 12; i++) {{
    const ang = (i / 12) * Math.PI * 2;
    const by = Math.cos(ang) * 1.72;
    const bz = Math.sin(ang) * 1.72;
    const cFase = colFases[i % 3];
    agregarCaja3D({{
      wx: 3.55, wy: 0.22, wz: 0.22, cx: 0, cy: by, cz: bz,
      color: cFase, partId: 'devanado_trifasico', exp: [0, Math.cos(ang)*1.3, Math.sin(ang)*1.3], alpha: 0.88
    }});
  }}
  agregarToro3D({{ R: 1.72, r: 0.20, segsR: 24, segsr: 8, cx: -1.72, cy: 0, cz: 0, eje: 'x', color: '#ff9f1c', partId: 'devanado_trifasico', exp: [-1.9, 0, 0], alpha: 0.88 }});
  agregarToro3D({{ R: 1.72, r: 0.20, segsR: 24, segsr: 8, cx: 1.72, cy: 0, cz: 0, eje: 'x', color: '#2ec4b6', partId: 'devanado_trifasico', exp: [1.9, 0, 0], alpha: 0.88 }});

  // 3. 16 Barras Conductoras Inclinadas (Skewed) de la Jaula de Ardilla
  const numBarras = 16;
  const rJaula = 1.18;
  for (let i = 0; i < numBarras; i++) {{
    const ang = (i / numBarras) * Math.PI * 2;
    const y1 = Math.cos(ang) * rJaula, z1 = Math.sin(ang) * rJaula;
    const y2 = Math.cos(ang + 0.22) * rJaula, z2 = Math.sin(ang + 0.22) * rJaula;
    const d = 0.085;
    agregarCara(
      [[-1.45, y1-d, z1], [-1.45, y1+d, z1], [1.45, y2+d, z2], [1.45, y2-d, z2]],
      '#ffca28', 'barras_jaula', [0, Math.cos(ang)*1.35, Math.sin(ang)*1.35], 0.98, 'rotor'
    );
    agregarCara(
      [[-1.45, y1, z1-d], [-1.45, y1, z1+d], [1.45, y2, z2+d], [1.45, y2, z2-d]],
      '#ffd166', 'barras_jaula', [0, Math.cos(ang)*1.35, Math.sin(ang)*1.35], 0.98, 'rotor'
    );
  }}

  // 4. Anillos de Cortocircuito (End Rings)
  agregarToro3D({{ R: rJaula, r: 0.15, segsR: 24, segsr: 10, cx: -1.45, cy: 0, cz: 0, eje: 'x', color: '#ff9f1c', partId: 'anillos_corto', exp: [-2.4, 0, 0], alpha: 0.96, anim: 'rotor' }});
  agregarToro3D({{ R: rJaula, r: 0.15, segsR: 24, segsr: 10, cx: 1.45, cy: 0, cz: 0, eje: 'x', color: '#ff9f1c', partId: 'anillos_corto', exp: [2.4, 0, 0], alpha: 0.96, anim: 'rotor' }});

  // 5. Núcleo Laminado del Rotor
  agregarCilindro3D({{
    r1: 1.05, r2: 1.05, len: 2.75, segs: 20, cx: 0, cy: 0, cz: 0, eje: 'x',
    color: '#48cae4', partId: 'nucleo_rotor', exp: [0, -1.9, 0], alpha: 0.62, anim: 'rotor'
  }});

  // 6. Eje Motriz (Shaft)
  agregarCilindro3D({{
    r1: 0.28, r2: 0.28, len: 5.5, segs: 16, cx: 0, cy: 0, cz: 0, eje: 'x',
    color: '#e0fbfc', partId: 'eje_motriz', exp: [-2.9, 0, 0], alpha: 0.95, anim: 'rotor'
  }});

  // 7. Campo Magnético Giratorio (Bs) en el Entrehierro
  agregarToro3D({{ R: 1.46, r: 0.045, segsR: 28, segsr: 6, cx: 0, cy: 0, cz: 0, eje: 'x', color: '#00ffcc', partId: 'campo_giratorio', exp: [0, 0, 2.3], alpha: 0.9, anim: 'field' }});
  for (let i = 0; i < 8; i++) {{
    particulasCampo.push({{ ang: (i / 8) * Math.PI * 2, radio: 1.46, x: (i % 2 === 0 ? -0.6 : 0.6) }});
  }}

}} else if (SPEC.preset === 'TRANSFORMER_3D') {{
  // Núcleo Ferromagnético
  agregarCaja3D({{ wx: 0.85, wy: 3.2, wz: 0.85, cx: -1.5, cy: 0, cz: 0, color: '#48cae4', partId: 'nucleo_fe', exp: [-0.8, 1.4, 0], alpha: 0.72 }});
  agregarCaja3D({{ wx: 0.85, wy: 3.2, wz: 0.85, cx: 1.5, cy: 0, cz: 0, color: '#48cae4', partId: 'nucleo_fe', exp: [0.8, 1.4, 0], alpha: 0.72 }});
  agregarCaja3D({{ wx: 3.85, wy: 0.8, wz: 0.85, cx: 0, cy: 1.6, cz: 0, color: '#48cae4', partId: 'nucleo_fe', exp: [0, 2.2, 0], alpha: 0.72 }});
  agregarCaja3D({{ wx: 3.85, wy: 0.8, wz: 0.85, cx: 0, cy: -1.6, cz: 0, color: '#48cae4', partId: 'nucleo_fe', exp: [0, -2.2, 0], alpha: 0.72 }});

  // Primario y Secundario
  for (let i = -4; i <= 4; i++) {{
    agregarToro3D({{ R: 0.78, r: 0.09, segsR: 20, segsr: 8, cx: -1.5, cy: i*0.24, cz: 0, eje: 'y', color: '#ff9f1c', partId: 'bobina_primaria', exp: [-2.2, 0, 0], alpha: 0.95 }});
  }}
  for (let i = -3; i <= 3; i++) {{
    agregarToro3D({{ R: 0.82, r: 0.12, segsR: 20, segsr: 8, cx: 1.5, cy: i*0.32, cz: 0, eje: 'y', color: '#ffca28', partId: 'bobina_secundaria', exp: [2.2, 0, 0], alpha: 0.95 }});
  }}
  [-1.5, -1.0, 1.0, 1.5].forEach(xp => {{
    agregarCilindro3D({{ r1: 0.14, r2: 0.18, len: 0.9, segs: 12, cx: xp, cy: 2.45, cz: 0, eje: 'y', color: '#e0fbfc', partId: 'aisladores_bushings', exp: [0, 2.5, 0], alpha: 0.92 }});
  }});
  for (let i = 0; i < 12; i++) particulasCampo.push({{ t: i / 12 }});

}} else if (SPEC.preset === 'EM_FIELD_SOLENOID') {{
  for (let i = -6; i <= 6; i++) {{
    agregarToro3D({{ R: 1.25, r: 0.09, segsR: 22, segsr: 8, cx: i*0.32, cy: 0, cz: 0, eje: 'x', color: '#ffca28', partId: 'bobina_helice', exp: [0, 1.8, 0], alpha: 0.95 }});
  }}
  [-0.55, 0, 0.55].forEach(yp => {{
    agregarCilindro3D({{ r1: 0.06, r2: 0.06, len: 5.2, segs: 10, cx: 0, cy: yp, cz: 0, eje: 'x', color: '#00ffcc', partId: 'lineas_internas', exp: [2.2, 0, 0], alpha: 0.9, anim: 'field' }});
  }});
  for (let i = 0; i < 4; i++) {{
    const ang = (i / 4) * Math.PI * 2;
    agregarToro3D({{ R: 2.1, r: 0.04, segsR: 26, segsr: 6, cx: 0, cy: Math.cos(ang)*1.0, cz: Math.sin(ang)*1.0, eje: 'z', color: '#00e5ff', partId: 'lineas_dipolo', exp: [0, Math.cos(ang)*1.8, Math.sin(ang)*1.8], alpha: 0.75, anim: 'field' }});
  }}
  [-1.4, 0, 1.4].forEach(xp => {{
    agregarToro3D({{ R: 1.65, r: 0.04, segsR: 22, segsr: 6, cx: xp, cy: 0, cz: 0, eje: 'x', color: '#ff9f1c', partId: 'anillos_equipotenciales', exp: [xp, -1.6, 0], alpha: 0.8, anim: 'rotor' }});
  }});
  for (let i = 0; i < 10; i++) particulasCampo.push({{ ang: (i / 10) * Math.PI * 2, radio: 0.0, x: (i/10)*5 - 2.5 }});

}} else if (SPEC.preset === 'ROVER_6WD') {{
  agregarCaja3D({{ wx: 2.8, wy: 0.75, wz: 1.85, cx: 0, cy: 0.1, cz: 0, color: '#00b4d8', partId: 'chasis_central', exp: [0, 1.5, 0], alpha: 0.88 }});
  [-1.35, 0, 1.35].forEach(xp => {{
    [-1.25, 1.25].forEach(zp => {{
      agregarCilindro3D({{ r1: 0.52, r2: 0.52, len: 0.36, segs: 18, cx: xp, cy: -0.75, cz: zp, eje: 'z', color: '#ffca28', partId: 'ruedas_6wd', exp: [xp*0.5, -1.2, zp*1.1], alpha: 0.94, anim: 'rotor' }});
      agregarCaja3D({{ wx: 0.14, wy: 0.85, wz: 0.14, cx: xp, cy: -0.32, cz: zp*0.85, color: '#90e0ef', partId: 'suspension_rocker', exp: [0, -0.8, zp], alpha: 0.9 }});
    }});
  }});
  agregarCilindro3D({{ r1: 0.09, r2: 0.09, len: 1.3, segs: 12, cx: 1.0, cy: 1.1, cz: -0.5, eje: 'y', color: '#e0fbfc', partId: 'mastil_camara', exp: [1.0, 2.0, -0.5], alpha: 0.92 }});
  agregarCaja3D({{ wx: 0.42, wy: 0.28, wz: 0.55, cx: 1.0, cy: 1.8, cz: -0.5, color: '#00ffcc', partId: 'mastil_camara', exp: [1.0, 2.2, -0.5], alpha: 0.96 }});
  agregarCaja3D({{ wx: 1.3, wy: 0.18, wz: 0.18, cx: 1.75, cy: 0.75, cz: 0.45, color: '#ff9f1c', partId: 'brazo_robotico', exp: [2.2, 1.0, 0.8], alpha: 0.95 }});

}} else {{
  // Constructor Universal para cualquier objeto generado por Gemini
  (SPEC.partes || []).forEach((p, idx) => {{
    const pos = p.pos || [0, 0, 0];
    const a = p.args || [1, 1, 1.8];
    const col = p.color || '#00e5ff';
    const exp = [(pos[0]||0)*0.8 + (idx%2?1.2:-1.2), (pos[1]||0)*0.8 + 0.8, (pos[2]||0)*0.8];
    const anim = p.anim === 'rotor' ? 'rotor' : (p.anim === 'field' ? 'field' : 'static');
    if (p.geom === 'torus') {{
      agregarToro3D({{ R: a[0]||1.3, r: a[1]||0.2, cx: pos[0]||0, cy: pos[1]||0, cz: pos[2]||0, color: col, partId: p.id, exp: exp, anim: anim }});
    }} else if (p.geom === 'box') {{
      agregarCaja3D({{ wx: a[0]||1.4, wy: a[1]||1.2, wz: a[2]||1.4, cx: pos[0]||0, cy: pos[1]||0, cz: pos[2]||0, color: col, partId: p.id, exp: exp, anim: anim }});
    }} else {{
      agregarCilindro3D({{ r1: a[0]||0.9, r2: a[1]||0.9, len: a[2]||2.0, cx: pos[0]||0, cy: pos[1]||0, cz: pos[2]||0, color: col, partId: p.id, exp: exp, anim: anim }});
    }}
  }});
}}

// =========================================================================
// 4. PROYECCIÓN 3D, Z-BUFFER, SOMBREADO STARK Y RAYCASTING POR CLIC
// =========================================================================
let anguloRotor = 0;
let anguloCampo = 0;
let poligonosEnPantalla = [];

function rotarPunto3D(x, y, z, rx, ry) {{
  // Rotación en Y (Yaw)
  const cy = Math.cos(ry), sy = Math.sin(ry);
  const x1 = x * cy + z * sy;
  const z1 = -x * sy + z * cy;
  // Rotación en X (Pitch)
  const cx = Math.cos(rx), sx = Math.sin(rx);
  const y2 = y * cx - z1 * sx;
  const z2 = y * sx + z1 * cx;
  return [x1, y2, z2];
}}

function proyectarPunto(pt) {{
  const fov = Math.min(W, H) * 0.82 * camZoom;
  const distCam = 9.2;
  const z = pt[2] + distCam;
  const escala = fov / Math.max(0.5, z);
  return [
    (W / 2) + camPanX + pt[0] * escala,
    (H / 2) + camPanY - pt[1] * escala,
    z,
    escala
  ];
}}

function puntoEnPoligono2D(px, py, pts2D) {{
  let dentro = false;
  for (let i = 0, j = pts2D.length - 1; i < pts2D.length; j = i++) {{
    const xi = pts2D[i][0], yi = pts2D[i][1];
    const xj = pts2D[j][0], yj = pts2D[j][1];
    const intersecta = ((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / ((yj - yi) || 1e-6) + xi);
    if (intersecta) dentro = !dentro;
  }}
  return dentro;
}}

function detectarClicEnPieza3D(mx, my) {{
  // Recorrer de adelante hacia atrás (polígonos más cercanos al usuario primero)
  for (let i = poligonosEnPantalla.length - 1; i >= 0; i--) {{
    const poly = poligonosEnPantalla[i];
    if (puntoEnPoligono2D(mx, my, poly.pts2D)) {{
      seleccionarPieza(poly.partId);
      return;
    }}
  }}
}}

function renderizarEscena() {{
  ctx.clearRect(0, 0, W, H);

  if (introEnsamble > 0.005) {{
    introEnsamble *= 0.92;
    camRotY += 0.045 * introEnsamble;
  }} else {{
    introEnsamble = 0.0;
  }}
  const expTotal = Math.min(1.4, factorExplosion + introEnsamble * 1.35);
  anguloCampo += 0.042 * factorVelocidad;
  anguloRotor += 0.042 * 0.955 * factorVelocidad; // Deslizamiento s real

  // 1. Dibujar Anillo y Rejilla Base Holográfica 3D
  ctx.save();
  ctx.strokeStyle = 'rgba(0, 229, 255, 0.25)';
  ctx.lineWidth = 1.2;
  for (let g = -3; g <= 3; g++) {{
    const a = proyectarPunto(rotarPunto3D(g * 1.1, -2.45, -3.3, camRotX, camRotY));
    const b = proyectarPunto(rotarPunto3D(g * 1.1, -2.45, 3.3, camRotX, camRotY));
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();

    const c = proyectarPunto(rotarPunto3D(-3.3, -2.45, g * 1.1, camRotX, camRotY));
    const d = proyectarPunto(rotarPunto3D(3.3, -2.45, g * 1.1, camRotX, camRotY));
    ctx.beginPath(); ctx.moveTo(c[0], c[1]); ctx.lineTo(d[0], d[1]); ctx.stroke();
  }}
  ctx.restore();

  // 2. Transformar y ordenar todas las caras 3D (Z-Buffer Painter's Algorithm)
  const carasParaDibujar = [];

  for (let i = 0; i < carasEscena.length; i++) {{
    const cara = carasEscena[i];
    if (cara.cutaway && modoCutaway && factorExplosion < 0.15) continue;
    if (cara.anim === 'field' && !mostrarCampos) continue;

    const ex = cara.exp[0] * expTotal;
    const ey = cara.exp[1] * expTotal;
    const ez = cara.exp[2] * expTotal;

    const rotPropia = (cara.anim === 'rotor') ? anguloRotor : ((cara.anim === 'field') ? anguloCampo : 0);
    const cr = Math.cos(rotPropia), sr = Math.sin(rotPropia);

    const vertsCam = [];
    const pts2D = [];
    let sumZ = 0;

    for (let j = 0; j < cara.verts.length; j++) {{
      let [vx, vy, vz] = cara.verts[j];
      if (rotPropia !== 0) {{
        const ny = vy * cr - vz * sr;
        const nz = vy * sr + vz * cr;
        vy = ny; vz = nz;
      }}
      vx += ex; vy += ey; vz += ez;
      const pRot = rotarPunto3D(vx, vy, vz, camRotX, camRotY);
      vertsCam.push(pRot);
      const pProj = proyectarPunto(pRot);
      pts2D.push(pProj);
      sumZ += pProj[2];
    }}

    // Calcular normal 3D para iluminación sombreada
    const u = [vertsCam[1][0]-vertsCam[0][0], vertsCam[1][1]-vertsCam[0][1], vertsCam[1][2]-vertsCam[0][2]];
    const v = [vertsCam[2][0]-vertsCam[0][0], vertsCam[2][1]-vertsCam[0][1], vertsCam[2][2]-vertsCam[0][2]];
    const nx = u[1]*v[2] - u[2]*v[1];
    const ny = u[2]*v[0] - u[0]*v[2];
    const nz = u[0]*v[1] - u[1]*v[0];
    const normLen = Math.hypot(nx, ny, nz) || 1;
    const luz = Math.abs((nx*0.35 + ny*0.55 - nz*0.75) / normLen);

    carasParaDibujar.push({{
      pts2D: pts2D,
      zMed: sumZ / cara.verts.length,
      rgb: cara.rgb,
      alpha: cara.alpha,
      luz: luz,
      partId: cara.partId
    }});
  }}

  // Ordenar de más lejano a más cercano
  carasParaDibujar.sort((a, b) => b.zMed - a.zMed);
  poligonosEnPantalla = carasParaDibujar;

  // 3. Pintar caras 3D y bordes láser holográficos
  for (let i = 0; i < carasParaDibujar.length; i++) {{
    const c = carasParaDibujar[i];
    const esSeleccionada = (piezaSeleccionadaId === 'ALL') || (piezaSeleccionadaId === c.partId);
    const brillo = 0.45 + 0.65 * c.luz + (piezaSeleccionadaId === c.partId ? 0.25 : 0);

    const r = Math.min(255, Math.round(c.rgb[0] * brillo));
    const g = Math.min(255, Math.round(c.rgb[1] * brillo));
    const b = Math.min(255, Math.round(c.rgb[2] * brillo));

    let opacidad = modoXRay ? 0.12 : (esSeleccionada ? c.alpha : 0.16);

    ctx.beginPath();
    ctx.moveTo(c.pts2D[0][0], c.pts2D[0][1]);
    for (let j = 1; j < c.pts2D.length; j++) {{
      ctx.lineTo(c.pts2D[j][0], c.pts2D[j][1]);
    }}
    ctx.closePath();

    ctx.fillStyle = `rgba(${{r}}, ${{g}}, ${{b}}, ${{opacidad}})`;
    ctx.fill();

    ctx.lineWidth = (piezaSeleccionadaId === c.partId) ? 1.8 : (modoXRay ? 1.1 : 0.65);
    ctx.strokeStyle = (piezaSeleccionadaId === c.partId)
      ? 'rgba(255, 215, 64, 0.95)'
      : `rgba(${{Math.min(255, r+50)}}, ${{Math.min(255, g+60)}}, 255, ${{esSeleccionada ? 0.55 : 0.15}})`;
    ctx.stroke();
  }}

  // 4. Dibujar Vectores y Partículas de Flujo Magnético en Tiempo Real
  if (mostrarCampos) {{
    ctx.save();
    particulasCampo.forEach((p, idx) => {{
      let px = 0, py = 0, pz = 0;
      if (SPEC.preset === 'SQUIRREL_CAGE_MOTOR') {{
        const a = p.ang + anguloCampo;
        px = p.x;
        py = Math.cos(a) * p.radio;
        pz = Math.sin(a) * p.radio;
      }} else if (SPEC.preset === 'TRANSFORMER_3D') {{
        const prog = (p.t + anguloCampo * 0.08) % 1.0;
        if (prog < 0.25) {{ px = -1.5 + (prog*4)*3.0; py = 1.6; pz = 0; }}
        else if (prog < 0.5) {{ px = 1.5; py = 1.6 - ((prog-0.25)*4)*3.2; pz = 0; }}
        else if (prog < 0.75) {{ px = 1.5 - ((prog-0.5)*4)*3.0; py = -1.6; pz = 0; }}
        else {{ px = -1.5; py = -1.6 + ((prog-0.75)*4)*3.2; pz = 0; }}
      }} else {{
        px = ((p.x + anguloCampo * 0.8 + 2.5) % 5.0) - 2.5;
        py = Math.sin(anguloCampo + idx) * 0.35;
        pz = Math.cos(anguloCampo + idx) * 0.35;
      }}
      const pr = proyectarPunto(rotarPunto3D(px, py, pz, camRotX, camRotY));
      ctx.beginPath();
      ctx.arc(pr[0], pr[1], Math.max(3, pr[3] * 0.09), 0, Math.PI * 2);
      ctx.fillStyle = '#00ffcc';
      ctx.shadowColor = '#00ffcc';
      ctx.shadowBlur = 12;
      ctx.fill();
    }});
    ctx.restore();
  }}

  requestAnimationFrame(renderizarEscena);
}}

requestAnimationFrame(renderizarEscena);

// Funciones de la Barra de Control Holográfica
function ajustarExplosion(val) {{
  factorExplosion = parseFloat(val) / 100.0;
}}

function toggleExplode() {{
  modoExplode = !modoExplode;
  document.getElementById('btn-explode').classList.toggle('active', modoExplode);
  const target = modoExplode ? 85 : 0;
  document.getElementById('slider-explode').value = target;
  ajustarExplosion(target);
}}

function toggleCutaway() {{
  modoCutaway = !modoCutaway;
  document.getElementById('btn-cutaway').classList.toggle('active', modoCutaway);
}}

function toggleXRay() {{
  modoXRay = !modoXRay;
  document.getElementById('btn-xray').classList.toggle('active', modoXRay);
}}

function toggleCampos() {{
  mostrarCampos = !mostrarCampos;
  document.getElementById('btn-field').classList.toggle('active', mostrarCampos);
}}

function ajustarVelocidad(val) {{
  factorVelocidad = parseFloat(val) / 100.0;
}}

function resetCamara() {{
  camRotX = 0.38;
  camRotY = -0.62;
  camZoom = 1.05;
  camPanX = 0;
  camPanY = 0;
  seleccionarPieza('ALL');
}}


function cerrarHologramaStark() {{
  document.body.classList.add(closing-hologram);
  setTimeout(() => {{ window.close(); }}, 540);
}}

function hablarExplicacionActual() {{
  if ('speechSynthesis' in window) {{
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(piezaActualTexto);
    u.lang = 'es-MX';
    u.rate = 1.05;
    window.speechSynthesis.speak(u);
  }}
}}
</script>
</body>
</html>"""

    ruta_tmp.write_text(html_content, encoding="utf-8")
    ruta_copia.write_text(html_content, encoding="utf-8")

    abierto = False
    for nav in ("google-chrome", "google-chrome-stable", "chromium"):
        if shutil.which(nav):
            subprocess.Popen(
                [nav, "--new-window", "--start-fullscreen", f"--app=file://{ruta_tmp}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            abierto = True
            break
    if not abierto:
        webbrowser.open_new(f"file://{ruta_tmp}")

    # Hilo que garantiza que la ventana 3D NUNCA quede minimizada y se ponga en Pantalla Completa al frente
    def _forzar_fullscreen_al_frente():
        import time
        for _ in range(8):
            time.sleep(0.35)
            if shutil.which("wmctrl"):
                try:
                    out = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
                    for l in out.splitlines():
                        partes = l.split(None, 3)
                        if len(partes) >= 4 and ("holograma 3d" in partes[3].lower() or "jarvis_hologram_3d" in partes[3].lower()):
                            wid = partes[0]
                            subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "remove,hidden,shaded"], stderr=subprocess.DEVNULL)
                            subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,fullscreen,above,maximized_vert,maximized_horz"], stderr=subprocess.DEVNULL)
                            subprocess.run(["wmctrl", "-i", "-a", wid], stderr=subprocess.DEVNULL)
                            if shutil.which("xdotool"):
                                subprocess.run(["xdotool", "windowactivate", wid], stderr=subprocess.DEVNULL)
                except Exception:
                    pass

    import threading
    threading.Thread(target=_forzar_fullscreen_al_frente, daemon=True).start()
    return ruta_tmp


def proyectar_modelo_3d_holografico(solicitud_usuario: str) -> str:
    tema = solicitud_usuario.lower()
    for pref in (
        "jarvis", "crea un modelo 3d de", "crea un modelo 3d", "modelo 3d holográfico de",
        "modelo 3d de", "muéstrame en 3d", "muestrame en 3d", "proyecta en 3d",
        "holograma 3d de", "holograma de", "en 3d", "modelo 3d",
    ):
        tema = tema.replace(pref, "").strip(" ,.:")
    tema_limpio = tema if len(tema) > 2 else solicitud_usuario

    escribir_estado_hud(
        "PROCESANDO",
        f"Renderizando Holograma 3D Interactivo: {tema_limpio.upper()}",
        visible=True,
        animacion="RESEARCH",
        app_actual=f"PROYECCIÓN CAD 3D // {tema_limpio.upper()[:28]}",
        progreso=65, efecto_transicion="ENTRADA",
    )

    especificacion = obtener_catalogo_planos_base(tema_limpio)
    if not especificacion:
        wiki_ctx = _resumen_wiki_3d(tema_limpio)
        especificacion = generar_plano_3d_universal_con_gemini(tema_limpio, wiki_ctx)

    construir_html_visor_3d_stark(especificacion)
    escribir_estado_hud("EN LÍNEA", f"Holograma 3D activo: {especificacion['titulo']}", visible=True, animacion="NORMAL", progreso=100)

    num_partes = len(especificacion.get("partes", []))
    salida = (
        f"He proyectado en su pantalla el modelo tridimensional holográfico de {especificacion['titulo']}, señor. "
        f"Consta de {num_partes} subsistemas interactivos: puede girarlo con sus dedos o el ratón, activar la vista explosiva "
        f"para desensamblar sus piezas en el aire, usar el corte interno y tocar cualquier componente para analizar su funcionamiento."
    )
    registrar_turno_conversacion(solicitud_usuario, salida)
    return salida
