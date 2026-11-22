#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Módulo de Memoria, Sincronización Dinámica de Classroom/Gmail y Auto-Depuración (Mark XVII)
- Elimina automáticamente tareas vencidas (reconoce fechas ISO, en español e inglés) y tareas ya concluidas.
- Sincroniza asignaciones próximas a entregar (ME I 1998, EyM, Robots Móviles) y correos reales de Gmail.
- Incluye sincronizador visual e IMAP para captar nuevas tareas de Google Classroom automáticamente.
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import collections
import datetime
import email
from email.header import decode_header
import imaplib
import json
import os
import random
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_MEMORIA = DIRECTORIO_BASE / "memoria_jarvis.json"
ARCHIVO_AGENDA = DIRECTORIO_BASE / "agenda.json"
ARCHIVO_ESTADO = DIRECTORIO_BASE / "ultimo_estado.json"
ARCHIVO_ESTADO_HUD = Path("/tmp/jarvis_hud_state.json")
ARCHIVO_ENV = DIRECTORIO_BASE / ".env"

SCHEMA_VERSION_ACTUAL = 17
HISTORIAL_CONVERSACION = collections.deque(maxlen=10)

MESES_MAP = {
    "ene": 1, "enero": 1, "jan": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "apr": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "aug": 8, "sep": 9, "septiembre": 9,
    "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12, "dec": 12,
}

MEMORIA_INICIAL = {
    "schema_version": SCHEMA_VERSION_ACTUAL,
    "personas": {
        "soren alessa": {
            "nombre": "Soren Alessa",
            "relacion": "Pareja de Max. Estudiante de Derecho, amante de los libros y los videojuegos, y es muy linda.",
            "notas": [
                "Es la novia de Max; comparte con él el gusto por los videojuegos y la lectura.",
                "Prioridad máxima en notificaciones y recordatorios personales de Max."
            ]
        },
        "ruben tapia": {
            "nombre": "Prof. Rubén Tapia Olvera",
            "relacion": "Profesor de Máquinas Eléctricas I (ME I 1998, grupo 2027-1) en la FI UNAM.",
            "notas": ["Asignó las tareas de Desempeño de Máquinas Eléctricas, Arranque de máquina asíncrona y Síntesis de redes eléctricas."]
        },
        "marco negrete": {
            "nombre": "Dr. Marco Antonio Negrete Villanueva",
            "relacion": "Jefe del Laboratorio LIRA (FI UNAM) y profesor de Robots Móviles 2027-1.",
            "notas": ["Supervisor de servicio social e investigación en navegación ROS 2 y redes neuronales."]
        },
        "ruth": {
            "nombre": "Ruth Getzemaní Moreno Cedano",
            "relacion": "Supervisora y compañera en el laboratorio LIRA.",
            "notas": ["Coordina el etiquetado en Labelme, dataset2026 y lectura de /cmd_vel en Notion."]
        },
        "ofelia": {
            "nombre": "Prof.ª María Ofelia Rodríguez Durán",
            "relacion": "Profesora de Electricidad y Magnetismo (G10-EyM-27-01).",
            "notas": ["Publicó el Video del Ejercicio 1 Tema 5 y los ejercicios de estudio de los Temas 4 y 5 para el examen colegiado."]
        },
        "juan emiliano": {
            "nombre": "Juan Emiliano Vázquez Vasallo",
            "relacion": "Co-fundador y CEO de SUMA.",
            "notas": ["Socio de Max en la dirección de SUMA."]
        }
    },
    "logros_y_hechos_completados": [
        {
            "fecha": "2026-11-17",
            "hecho": "Concluyó y entregó la Práctica 04 (Entrenamiento de una red neuronal) de Robots Móviles y la Actividad de Campo magnético del solenoide de Electricidad y Magnetismo."
        },
        {
            "fecha": "2026-11-18",
            "hecho": "Actualizó J.A.R.V.I.S. a la versión Mark XVII con sincronización automática de Google Classroom y Gmail."
        }
    ],
    "classroom_asignaciones": [
        {
            "id": 1,
            "curso": "ME I (1998) 2027-1 Máquinas Eléctricas I",
            "titulo": "Desempeño de Máquinas Eléctricas",
            "entrega": "2026-11-19 23:59",
            "completado": False
        },
        {
            "id": 2,
            "curso": "ME I (1998) 2027-1 Máquinas Eléctricas I",
            "titulo": "Arranque máquina asíncrona",
            "entrega": "2026-11-20 23:59",
            "completado": False
        },
        {
            "id": 3,
            "curso": "ME I (1998) 2027-1 Máquinas Eléctricas I",
            "titulo": "Síntesis para evaluación cuantitativa de redes eléctricas",
            "entrega": "2026-11-23 23:59",
            "completado": False
        }
    ],
    "correos_importantes": [
        {
            "id": 1,
            "remitente": "Prof.ª María Ofelia Rodríguez (EyM G10)",
            "asunto": "Nuevo material: VIDEO EJERCICIO 1 TEMA 5 y Ejercicios Colegiado",
            "resumen": "Ver video del inicio al min 9:54 y del 17:06 al final; revisar problemas 2 al 6 del Tema 5 y ejercicios del Tema 4.",
            "vencimiento": "2026-11-24 23:59",
            "completado": False
        },
        {
            "id": 2,
            "remitente": "Prof. Rubén Tapia Olvera (ME I 1998)",
            "asunto": "Nuevo material en Classroom: Pres MI",
            "resumen": "Material de presentación publicado en Máquinas Eléctricas I y entregas de esta semana.",
            "vencimiento": "2026-11-23 23:59",
            "completado": False
        },
        {
            "id": 3,
            "remitente": "Dr. Marco Negrete (Robots Móviles 2027-1)",
            "asunto": "Aviso de clase: Hola a todos, los veo 3:30 PM",
            "resumen": "Notificación reciente del Dr. Marco Negrete en Robots Móviles.",
            "vencimiento": "2026-11-20 23:59",
            "completado": False
        },
        {
            "id": 4,
            "remitente": "Academia.edu Mentions",
            "asunto": "Guzman Ortiz, someone cited your work",
            "resumen": "Mención de 'Guzman Ortiz Luis Maximiliano' en 'Waves of Discovery – From Sound to Spacetime'.",
            "vencimiento": "2026-11-25 23:59",
            "completado": False
        }
    ],
    "mensajes_pendientes": [
        {
            "id": 1,
            "plataforma": "WhatsApp / Personal",
            "remitente": "Soren Alessa",
            "asunto": "Mensajes prioritarios de Soren Alessa",
            "vencimiento": "2026-11-30 23:59",
            "completado": False
        }
    ],
    "proyectos_activos": [
        {
            "id": 1,
            "proyecto": "UNAM SPACE — Rover",
            "tarea": "Robustificar electrónica de potencia (BTS7960) y control Xbox del rover",
            "vencimiento": "2026-12-15 23:59",
            "completado": False
        },
        {
            "id": 2,
            "proyecto": "LIRA — Navegación ROS 2",
            "tarea": "Implementar Mapa de Costos 2D y alcanzar meta de etiquetado en Labelme",
            "vencimiento": "2026-12-15 23:59",
            "completado": False
        }
    ],
    "historial_archivados": [],
    "completados_permanentes": [
        "Práctica 04 - Entrenamiento de una red neuronal",
        "Actividad Campo magnético del solenoide y líneas de campo",
        "Trending in BioRobotics Lab: Repositorio X500_TMR2027",
        "Nuevo mensaje para el intercambio LIRA-Navidad"
    ]
}


def _normalizar_texto_comparacion(texto: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")
    mapa_nums = {
        "uno": "1", "primero": "1", "primera": "1",
        "dos": "2", "segundo": "2", "segunda": "2",
        "tres": "3", "tercero": "3", "tercera": "3",
        "cuatro": "4", "cuarto": "4", "cuarta": "4",
        "cinco": "5", "quinto": "5",
    }
    for pal, dig in mapa_nums.items():
        s = re.sub(rf"\b{pal}\b", dig, s)
    s = re.sub(r"\b0+(\d+)\b", r"\1", s)
    return s


def parsear_fecha_flexible(fecha_str: str) -> datetime.datetime | None:
    """
    Convierte cualquier cadena de fecha ('2026-11-19 23:59', 'Hoy, 17 de noviembre de 2026',
    'Due Nov 19', '19 de noviembre') en un objeto datetime exacto para saber si ya venció.
    """
    if not fecha_str:
        return None
    texto = str(fecha_str).strip()
    ahora = datetime.datetime.now()

    # 1. Intentar formatos ISO estándar
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(texto, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt
        except Exception:
            pass

    # 2. Intentar fechas en español: "17 de noviembre de 2026" o "19 de nov"
    t_low = _normalizar_texto_comparacion(texto)
    m_es = re.search(r"(\d{1,2})\s*(?:de\s+)?([a-z]+)(?:\s*(?:de\s+)?(\d{4}))?", t_low)
    if m_es:
        dia = int(m_es.group(1))
        mes_txt = m_es.group(2)[:3]
        anio = int(m_es.group(3)) if m_es.group(3) else ahora.year
        mes = MESES_MAP.get(m_es.group(2)) or MESES_MAP.get(mes_txt)
        if mes and 1 <= dia <= 31:
            try:
                return datetime.datetime(anio, mes, dia, 23, 59, 59)
            except Exception:
                pass

    # 3. Intentar formato inglés de correos de Classroom: "Due Nov 19" o "Nov 20, 2026"
    m_en = re.search(r"([a-z]{3,9})\s+(\d{1,2})(?:,?\s*(\d{4}))?", t_low)
    if m_en:
        mes_txt = m_en.group(1)[:3]
        dia = int(m_en.group(2))
        anio = int(m_en.group(3)) if m_en.group(3) else ahora.year
        mes = MESES_MAP.get(m_en.group(1)) or MESES_MAP.get(mes_txt)
        if mes and 1 <= dia <= 31:
            try:
                return datetime.datetime(anio, mes, dia, 23, 59, 59)
            except Exception:
                pass

    return None


def formatear_fecha_humana_classroom(fecha_str: str) -> str:
    """Devuelve etiquetas idénticas a Google Classroom: 'Mañana, 23:59 (19 Nov)', 'Viernes, 23:59 (20 Nov)', etc."""
    dt = parsear_fecha_flexible(fecha_str)
    if not dt:
        return fecha_str
    hoy = datetime.date.today()
    dias_diff = (dt.date() - hoy).days
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_cortos = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    etiqueta_fecha = f"{dt.day} {meses_cortos[dt.month]}"
    hora_txt = dt.strftime("%H:%M")

    if dias_diff == 0:
        return f"Hoy, {hora_txt} ({etiqueta_fecha})"
    if dias_diff == 1:
        return f"Mañana, {hora_txt} ({etiqueta_fecha})"
    if 2 <= dias_diff <= 6:
        return f"{dias_semana[dt.weekday()]}, {hora_txt} ({etiqueta_fecha})"
    return f"{dias_semana[dt.weekday()]} {etiqueta_fecha}, {hora_txt}"


def _fecha_ya_vencio(fecha_str: str) -> bool:
    dt = parsear_fecha_flexible(fecha_str)
    if not dt:
        return False
    return datetime.datetime.now() > dt


def cargar_api_key_memoria() -> str:
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


def obtener_historial_frases_dichas() -> list[str]:
    if ARCHIVO_ESTADO.exists():
        try:
            datos = json.loads(ARCHIVO_ESTADO.read_text(encoding="utf-8"))
            return datos.get("historial_frases_dichas", [])
        except Exception:
            pass
    return []


def registrar_frase_dicha(frase: str) -> None:
    if not frase:
        return
    estado = {}
    if ARCHIVO_ESTADO.exists():
        try:
            estado = json.loads(ARCHIVO_ESTADO.read_text(encoding="utf-8"))
        except Exception:
            estado = {}
    historial = estado.get("historial_frases_dichas", [])
    historial.append(frase.strip())
    estado["historial_frases_dichas"] = historial[-45:]
    try:
        DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
        ARCHIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def registrar_turno_conversacion(usuario: str, respuesta_jarvis: str) -> None:
    HISTORIAL_CONVERSACION.append({
        "hora": datetime.datetime.now().strftime("%H:%M:%S"),
        "max": usuario,
        "jarvis": respuesta_jarvis,
    })
    registrar_frase_dicha(respuesta_jarvis)


def sintetizar_respuesta_unica_contextual(
    pregunta_usuario: str,
    hechos_base: str,
    incluir_punto_de_vista: bool = True,
) -> str:
    api_key = cargar_api_key_memoria()
    frases_previas = obtener_historial_frases_dichas()[-10:]
    contexto_turnos = " | ".join(
        f"Max: '{t['max']}' -> Jarvis: '{t['jarvis']}'"
        for t in list(HISTORIAL_CONVERSACION)[-4:]
    )

    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            instruccion_opinion = (
                "Incluye además de forma natural tu propio punto de vista, consejo o apreciación inteligente como J.A.R.V.I.S."
                if incluir_punto_de_vista
                else "Mantén el comentario ágil, elegante y directo."
            )
            prompt = (
                f"Actúa como J.A.R.V.I.S. (el asistente de Tony Stark, hablando en español de México formal y leal a su creador Max). "
                f"Solicitud o comentario actual de Max: '{pregunta_usuario}'. "
                f"Datos reales y verificados que debes comunicar con total certeza (PROHIBIDO mencionar la Práctica 04 o la actividad del solenoide como pendientes porque ya concluyeron): {hechos_base}. "
                f"Contexto reciente de la conversación: {contexto_turnos}. "
                f"Frases que dijiste recientemente y que TIENES PROHIBIDO REPETIR: {frases_previas}. "
                f"Redacta una respuesta fresca y original de 2 a 3 oraciones fluidas para ser leídas en voz alta, sin asteriscos ni markdown. {instruccion_opinion}"
            )
            for mod in ("models/gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash", "gemini-2.0-flash"):
                try:
                    res = client.models.generate_content(model=mod, contents=prompt)
                    texto_gen = (res.text or "").replace("*", "").replace("#", "").strip()
                    if texto_gen and texto_gen not in frases_previas:
                        registrar_turno_conversacion(pregunta_usuario, texto_gen)
                        return texto_gen
                except Exception:
                    continue
        except Exception:
            pass

    prefijos = [
        "Consultando sus registros actualizados en tiempo real, señor:",
        "Por supuesto, Max. Le comparto el estado vigente:",
        "Enseguida, señor. Con su base de datos depurada:",
    ]
    elegida = f"{random.choice(prefijos)} {hechos_base}"
    registrar_turno_conversacion(pregunta_usuario, elegida)
    return elegida


def cargar_memoria() -> dict:
    DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO_MEMORIA.exists():
        guardar_memoria(MEMORIA_INICIAL)
        return json.loads(json.dumps(MEMORIA_INICIAL))
    try:
        datos = json.loads(ARCHIVO_MEMORIA.read_text(encoding="utf-8"))
        # Si el archivo en disco era de una versión anterior (< 17), migrar a la base limpia actual conservando personas/notas nuevas
        if datos.get("schema_version", 0) < SCHEMA_VERSION_ACTUAL:
            nueva = json.loads(json.dumps(MEMORIA_INICIAL))
            for k_p, v_p in datos.get("personas", {}).items():
                if k_p != "isabel" and k_p not in nueva["personas"]:
                    nueva["personas"][k_p] = v_p
            guardar_memoria(nueva)
            return nueva
        return datos
    except Exception:
        guardar_memoria(MEMORIA_INICIAL)
        return json.loads(json.dumps(MEMORIA_INICIAL))


def guardar_memoria(datos: dict) -> None:
    DIRECTORIO_BASE.mkdir(parents=True, exist_ok=True)
    ARCHIVO_MEMORIA.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def depurar_y_actualizar_todo_el_contexto() -> dict:
    """
    Revisa automáticamente Classroom, Correos, Mensajes, Proyectos y agenda.json.
    Elimina al instante cualquier tarea cuya fecha haya vencido o que esté en completados_permanentes,
    y ordena las asignaciones de Classroom de la más próxima a vencer a la más lejana.
    """
    mem = cargar_memoria()
    lista_negra = set(_normalizar_texto_comparacion(x) for x in mem.get("completados_permanentes", []))
    modificado_mem = False

    def _esta_en_lista_negra(titulo_str: str) -> bool:
        t_norm = _normalizar_texto_comparacion(titulo_str)
        if not t_norm:
            return False
        return any(bn and (bn in t_norm or t_norm in bn) for bn in lista_negra)

    # 1. Depurar y ordenar Google Classroom por fecha de vencimiento más próxima
    cr_activas = []
    for item in mem.get("classroom_asignaciones", []):
        vencio = _fecha_ya_vencio(item.get("entrega", ""))
        if item.get("completado", False) or vencio or _esta_en_lista_negra(item.get("titulo", "")):
            modificado_mem = True
        else:
            item["entrega_humana"] = formatear_fecha_humana_classroom(item.get("entrega", ""))
            cr_activas.append(item)

    cr_activas.sort(key=lambda x: parsear_fecha_flexible(x.get("entrega", "")) or datetime.datetime(2099, 12, 31))
    mem["classroom_asignaciones"] = cr_activas

    # 2. Depurar Correos Importantes
    correos_activos = []
    for c in mem.get("correos_importantes", []):
        vencio = _fecha_ya_vencio(c.get("vencimiento", ""))
        if c.get("completado", False) or vencio or _esta_en_lista_negra(c.get("asunto", "")):
            modificado_mem = True
        else:
            correos_activos.append(c)
    mem["correos_importantes"] = correos_activos

    # 3. Depurar Mensajes
    msgs_activos = []
    for m in mem.get("mensajes_pendientes", []):
        vencio = _fecha_ya_vencio(m.get("vencimiento", ""))
        if m.get("completado", False) or vencio or _esta_en_lista_negra(m.get("asunto", "")):
            modificado_mem = True
        else:
            msgs_activos.append(m)
    mem["mensajes_pendientes"] = msgs_activos

    # 4. Depurar Proyectos
    proys_activos = []
    for pr in mem.get("proyectos_activos", []):
        vencio = _fecha_ya_vencio(pr.get("vencimiento", ""))
        if pr.get("completado", False) or vencio or _esta_en_lista_negra(pr.get("tarea", "")):
            modificado_mem = True
        else:
            proys_activos.append(pr)
    mem["proyectos_activos"] = proys_activos

    if modificado_mem:
        guardar_memoria(mem)

    # 5. Depurar Agenda Externa (~/jarvis/agenda.json)
    if ARCHIVO_AGENDA.exists():
        try:
            ag = json.loads(ARCHIVO_AGENDA.read_text(encoding="utf-8"))
            pendientes_vigentes = []
            cambio_ag = False
            for p in ag.get("pendientes", []):
                t_p = p.get("titulo", "")
                vencio_fecha = _fecha_ya_vencio(p.get("vencimiento", "")) or _fecha_ya_vencio(t_p)
                if p.get("completado", False) or vencio_fecha or _esta_en_lista_negra(t_p):
                    cambio_ag = True
                else:
                    pendientes_vigentes.append(p)
            if cambio_ag:
                ag["pendientes"] = pendientes_vigentes
                ARCHIVO_AGENDA.write_text(json.dumps(ag, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return mem


def notificar_refresco_hud(mensaje: str = "Listas de Classroom y Gmail sincronizadas.") -> None:
    try:
        hud_data = {}
        if ARCHIVO_ESTADO_HUD.exists():
            hud_data = json.loads(ARCHIVO_ESTADO_HUD.read_text(encoding="utf-8"))
        hud_data["subtexto"] = mensaje
        hud_data["efecto_transicion"] = "PORTAL"
        hud_data["timestamp"] = datetime.datetime.now().strftime("%H:%M:%S.%f")
        ARCHIVO_ESTADO_HUD.write_text(json.dumps(hud_data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def marcar_entregado_o_actualizar_item(texto_referencia: str) -> str:
    """
    Marca como concluida/entregada cualquier tarea de Classroom, correo o pendiente mencionado
    y la añade a completados_permanentes para que desaparezca inmediatamente del HUD.
    """
    mem = depurar_y_actualizar_todo_el_contexto()
    ref_norm = _normalizar_texto_comparacion(texto_referencia)

    ref_limpia = ref_norm
    for pref in (
        "jarvis", "yarvis", "por favor", "ya entregue", "ya hice", "ya termine", "ya conclui",
        "ya complete", "ya revise", "ya conteste", "marca como completado", "marca como completada",
        "marcalo como completado", "actualiza", "elimina", "quita", "borra", "tacha", "ya quedo",
    ):
        ref_limpia = ref_limpia.replace(pref, " ").strip()

    stopwords = {
        "el", "la", "los", "las", "de", "del", "en", "con", "por", "para", "que", "mi", "mis",
        "un", "una", "lo", "al", "se", "me", "como", "hoy", "ayer", "todas", "todos", "todo",
    }
    palabras_usuario = [w for w in re.findall(r"[a-z0-9]+", ref_limpia) if w not in stopwords and (len(w) >= 3 or w.isdigit())]
    raices_usuario = [w[:5] if len(w) >= 5 else w for w in palabras_usuario]

    eliminados = []
    ahora_iso = datetime.date.today().isoformat()
    lista_negra = mem.setdefault("completados_permanentes", [])

    def _coincide_inteligente(texto_objetivo: str, id_item: int = -1) -> bool:
        obj_norm = _normalizar_texto_comparacion(texto_objetivo)
        if id_item > 0 and str(id_item) in palabras_usuario and any(k in ref_norm for k in ("numero", "id", "pendiente", "tarea", "practica", "actividad")):
            return True
        if any(k in ref_norm for k in ("desempeno", "aplicabilidad")) and "desempeno" in obj_norm:
            return True
        if any(k in ref_norm for k in ("arranque", "asincrona", "asincrono")) and ("arranque" in obj_norm or "asincron" in obj_norm):
            return True
        if any(k in ref_norm for k in ("sintesis", "evaluacion cuantitativa", "redes electricas")) and ("sintesis" in obj_norm or "redes electricas" in obj_norm):
            return True
        if any(k in ref_norm for k in ("practica 4", "red neuronal", "negrete")) and ("practica 4" in obj_norm or "negrete" in obj_norm):
            return True
        if any(k in ref_norm for k in ("solenoide", "ofelia", "tema 5", "tema 4", "colegiado")) and any(x in obj_norm for x in ("solenoide", "ofelia", "tema 5", "colegiado")):
            return True
        if any(k in ref_norm for k in ("mapa de costos", "costmap", "rover del lira")) and "mapa de costos" in obj_norm:
            return True
        if any(k in ref_norm for k in ("labelme", "etiquetar", "etiquetado", "600 etiquetas")) and ("labelme" in obj_norm or "etiquet" in obj_norm):
            return True
        if any(k in ref_norm for k in ("academia", "cited", "mencion")) and "academia" in obj_norm:
            return True

        palabras_esp = [r for r in raices_usuario if r not in ("class", "tarea", "pendi", "asign", "activ", "corre")]
        if not palabras_esp:
            return False
        return sum(1 for r in palabras_esp if r in obj_norm) >= 1

    for item in mem.get("classroom_asignaciones", []):
        if _coincide_inteligente(f"{item.get('curso', '')} {item.get('titulo', '')}", item.get("id", -1)):
            item["completado"] = True
            lista_negra.append(item["titulo"])
            eliminados.append(f"Classroom: {item['titulo']}")

    for c in mem.get("correos_importantes", []):
        if _coincide_inteligente(f"{c.get('remitente', '')} {c.get('asunto', '')} {c.get('resumen', '')}", c.get("id", -1)):
            c["completado"] = True
            lista_negra.append(c["asunto"])
            eliminados.append(f"Correo: {c['asunto']}")

    for m in mem.get("mensajes_pendientes", []):
        if _coincide_inteligente(f"{m.get('remitente', '')} {m.get('asunto', '')}", m.get("id", -1)):
            m["completado"] = True
            lista_negra.append(m["asunto"])
            eliminados.append(f"Mensaje de {m['remitente']}")

    for pr in mem.get("proyectos_activos", []):
        if _coincide_inteligente(f"{pr.get('proyecto', '')} {pr.get('tarea', '')}", pr.get("id", -1)):
            pr["completado"] = True
            lista_negra.append(pr["tarea"])
            eliminados.append(f"Proyecto: {pr['tarea']}")

    if ARCHIVO_AGENDA.exists():
        try:
            ag = json.loads(ARCHIVO_AGENDA.read_text(encoding="utf-8"))
            for p in ag.get("pendientes", []):
                if not p.get("completado", False) and _coincide_inteligente(f"{p.get('categoria', '')} {p.get('titulo', '')}", p.get("id", -1)):
                    p["completado"] = True
                    lista_negra.append(p["titulo"])
                    eliminados.append(f"[{p.get('categoria')}] {p.get('titulo')}")
            ARCHIVO_AGENDA.write_text(json.dumps(ag, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    if eliminados:
        for el in eliminados:
            mem.setdefault("logros_y_hechos_completados", []).append({"fecha": ahora_iso, "hecho": f"Concluido: {el}"})
        guardar_memoria(mem)

    mem_limpia = depurar_y_actualizar_todo_el_contexto()
    notificar_refresco_hud()

    cr_vigentes = [f"{t['titulo']} ({formatear_fecha_humana_classroom(t['entrega'])})" for t in mem_limpia.get("classroom_asignaciones", [])]
    resumen_cr = "; ".join(cr_vigentes) if cr_vigentes else "ninguna tarea pendiente"

    if eliminados:
        hechos = f"Se retiraron permanentemente: {'; '.join(eliminados)}. Las asignaciones próximas a entregar en Google Classroom son: {resumen_cr}."
    else:
        hechos = f"Base de datos depurada. Sus asignaciones vigentes próximas a entregar en Google Classroom son: {resumen_cr}."
    return sintetizar_respuesta_unica_contextual(texto_referencia, hechos, incluir_punto_de_vista=True)


def sincronizar_classroom_y_gmail_desde_pantalla(ruta_imagen: Path) -> str:
    """
    Si Max tiene abierto Google Classroom (To-do / Pendientes) o Gmail en su pantalla,
    extrae con Gemini Vision las nuevas tareas, fechas de entrega o correos y actualiza memoria_jarvis.json.
    """
    api_key = cargar_api_key_memoria()
    if not api_key or not ruta_imagen or not ruta_imagen.exists():
        return ""
    try:
        from google import genai
        from PIL import Image
        client = genai.Client(api_key=api_key)
        img = Image.open(ruta_imagen)
        img.thumbnail((1920, 1080))
        hoy_str = datetime.date.today().isoformat()
        prompt = (
            f"Hoy es {hoy_str}. Analiza esta captura de pantalla de Google Classroom o Gmail de Max.\n"
            f"Extrae las tareas pendientes próximas a entregar (con su fecha convertida a formato 'YYYY-MM-DD 23:59') "
            f"y/o correos importantes visibles.\n"
            f"Devuelve ÚNICAMENTE un JSON válido (sin markdown) con este formato:\n"
            f'{{"tareas_classroom": [{{"curso": "Nombre del curso", "titulo": "Título exacto de la tarea", "entrega": "YYYY-MM-DD 23:59"}}], '
            f'"correos": [{{"remitente": "Nombre", "asunto": "Asunto", "resumen": "Breve detalle"}}]}}'
        )
        for mod in ("models/gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash"):
            try:
                res = client.models.generate_content(model=mod, contents=[img, prompt])
                m = re.search(r"\{.*\}", (res.text or ""), re.DOTALL)
                if m:
                    extraido = json.loads(m.group(0))
                    mem = cargar_memoria()
                    lista_negra = set(_normalizar_texto_comparacion(x) for x in mem.get("completados_permanentes", []))
                    hubo_cambios = False

                    tareas_nuevas = extraido.get("tareas_classroom", [])
                    if tareas_nuevas:
                        actuales_norm = {_normalizar_texto_comparacion(t["titulo"]): t for t in mem.get("classroom_asignaciones", [])}
                        for tn in tareas_nuevas:
                            tit = (tn.get("titulo") or "").strip()
                            ent = (tn.get("entrega") or "").strip()
                            t_norm = _normalizar_texto_comparacion(tit)
                            if tit and t_norm not in lista_negra and not _fecha_ya_vencio(ent):
                                actuales_norm[t_norm] = {
                                    "id": len(actuales_norm) + 1,
                                    "curso": tn.get("curso", "Google Classroom"),
                                    "titulo": tit,
                                    "entrega": ent,
                                    "completado": False,
                                }
                                hubo_cambios = True
                        mem["classroom_asignaciones"] = list(actuales_norm.values())

                    correos_nuevos = extraido.get("correos", [])
                    if correos_nuevos:
                        c_actuales = {_normalizar_texto_comparacion(c["asunto"]): c for c in mem.get("correos_importantes", [])}
                        for cn in correos_nuevos:
                            asunto = (cn.get("asunto") or "").strip()
                            a_norm = _normalizar_texto_comparacion(asunto)
                            if asunto and a_norm not in lista_negra:
                                c_actuales[a_norm] = {
                                    "id": len(c_actuales) + 1,
                                    "remitente": cn.get("remitente", "Gmail"),
                                    "asunto": asunto,
                                    "resumen": cn.get("resumen", "Correo reciente en bandeja."),
                                    "vencimiento": "2026-11-28 23:59",
                                    "completado": False,
                                }
                                hubo_cambios = True
                        mem["correos_importantes"] = list(c_actuales.values())[:6]

                    if hubo_cambios:
                        guardar_memoria(mem)
                        depurar_y_actualizar_todo_el_contexto()
                        notificar_refresco_hud("Classroom y Gmail sincronizados ópticamente.")
                        return "Sincronización visual con Classroom/Gmail completada."
                    break
            except Exception:
                continue
    except Exception:
        pass
    return ""


def sincronizar_imap_gmail_si_disponible() -> None:
    """
    Si GMAIL_APP_PASSWORD está configurado en ~/jarvis/.env, descarga en segundo plano
    nuevas tareas de Google Classroom (extrayendo su fecha 'Due Month Day') y correos importantes.
    """
    user_mail = os.environ.get("GMAIL_USER", "themaybeman1203@gmail.com")
    app_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if ARCHIVO_ENV.exists() and not app_pass:
        for linea in ARCHIVO_ENV.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("GMAIL_APP_PASSWORD="):
                app_pass = linea.split("=", 1)[1].strip().strip('"').strip("'")
            elif linea.strip().startswith("GMAIL_USER="):
                user_mail = linea.split("=", 1)[1].strip().strip('"').strip("'")
    if not app_pass:
        return

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=5)
        mail.login(user_mail, app_pass)
        mail.select("inbox")
        _, data = mail.search(None, "(UNSEEN)")
        ids = data[0].split()[-15:]
        mem = cargar_memoria()
        lista_negra = set(_normalizar_texto_comparacion(x) for x in mem.get("completados_permanentes", []))
        tareas_dict = {_normalizar_texto_comparacion(t["titulo"]): t for t in mem.get("classroom_asignaciones", [])}
        correos_dict = {_normalizar_texto_comparacion(c["asunto"]): c for c in mem.get("correos_importantes", [])}
        modificado = False

        for num in reversed(ids):
            _, msg_data = mail.fetch(num, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subj_raw = decode_header(msg.get("Subject", ""))[0]
                    subj = subj_raw[0].decode(subj_raw[1] or "utf-8", errors="ignore") if isinstance(subj_raw[0], bytes) else str(subj_raw[0])
                    from_raw = decode_header(msg.get("From", ""))[0]
                    remitente = from_raw[0].decode(from_raw[1] or "utf-8", errors="ignore") if isinstance(from_raw[0], bytes) else str(from_raw[0])

                    cuerpo_txt = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    cuerpo_txt = payload.decode("utf-8", errors="ignore")
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            cuerpo_txt = payload.decode("utf-8", errors="ignore")

                    if "classroom.google.com" in remitente.lower():
                        # Extraer si es una asignación ('New assignment' / 'Nueva tarea')
                        if "new assignment" in subj.lower() or "nueva tarea" in subj.lower():
                            titulo_limpio = re.sub(r"^(New assignment|Nueva tarea):\s*", "", subj, flags=re.IGNORECASE).strip(' "')
                            t_norm = _normalizar_texto_comparacion(titulo_limpio)
                            m_due = re.search(r"Due\s+([A-Za-z]+\s+\d{1,2})", cuerpo_txt)
                            dt_due = parsear_fecha_flexible(m_due.group(1)) if m_due else (datetime.datetime.now() + datetime.timedelta(days=5))
                            entrega_iso = dt_due.strftime("%Y-%m-%d 23:59") if dt_due else "2026-11-25 23:59"
                            if t_norm not in lista_negra and not _fecha_ya_vencio(entrega_iso):
                                tareas_dict[t_norm] = {
                                    "id": len(tareas_dict) + 1,
                                    "curso": remitente.split("<")[0].replace("(Classroom)", "").strip(),
                                    "titulo": titulo_limpio,
                                    "entrega": entrega_iso,
                                    "completado": False,
                                }
                                modificado = True
                        else:
                            # Es un anuncio o material de clase en Classroom -> va a Correos/Avisos por atender
                            a_norm = _normalizar_texto_comparacion(subj)
                            if a_norm not in lista_negra and "due tomorrow" not in subj.lower():
                                correos_dict[a_norm] = {
                                    "id": len(correos_dict) + 1,
                                    "remitente": remitente.split("<")[0].strip(),
                                    "asunto": subj,
                                    "resumen": "Aviso o material reciente publicado en Google Classroom.",
                                    "vencimiento": (datetime.datetime.now() + datetime.timedelta(days=6)).strftime("%Y-%m-%d 23:59"),
                                    "completado": False,
                                }
                                modificado = True
                    elif not any(spam in remitente.lower() for spam in ("temu", "shein", "aliexpress", "steren", "samsung", "reddit")):
                        a_norm = _normalizar_texto_comparacion(subj)
                        if a_norm not in lista_negra:
                            correos_dict[a_norm] = {
                                "id": len(correos_dict) + 1,
                                "remitente": remitente.split("<")[0].strip(),
                                "asunto": subj,
                                "resumen": "Correo prioritario reciente en bandeja de entrada.",
                                "vencimiento": (datetime.datetime.now() + datetime.timedelta(days=6)).strftime("%Y-%m-%d 23:59"),
                                "completado": False,
                            }
                            modificado = True
        mail.logout()
        if modificado:
            mem["classroom_asignaciones"] = list(tareas_dict.values())
            mem["correos_importantes"] = list(correos_dict.values())[:6]
            guardar_memoria(mem)
            depurar_y_actualizar_todo_el_contexto()
    except Exception:
        pass


def agregar_nuevo_item_contextual(tipo: str, titulo: str, categoria_o_curso: str = "General", vencimiento: str = "") -> str:
    mem = depurar_y_actualizar_todo_el_contexto()
    t_low = tipo.lower()
    if "classroom" in t_low:
        nuevo_id = max([x.get("id", 0) for x in mem.get("classroom_asignaciones", [])], default=0) + 1
        dt_v = parsear_fecha_flexible(vencimiento)
        entrega_str = dt_v.strftime("%Y-%m-%d 23:59") if dt_v else (vencimiento or "2026-11-25 23:59")
        mem.setdefault("classroom_asignaciones", []).append({
            "id": nuevo_id, "curso": categoria_o_curso, "titulo": titulo,
            "entrega": entrega_str, "completado": False
        })
        guardar_memoria(mem)
        depurar_y_actualizar_todo_el_contexto()
        notificar_refresco_hud()
        return sintetizar_respuesta_unica_contextual(titulo, f"Nueva asignación de Classroom registrada: {titulo} ({formatear_fecha_humana_classroom(entrega_str)}).", False)
    elif "correo" in t_low or "gmail" in t_low:
        nuevo_id = max([x.get("id", 0) for x in mem.get("correos_importantes", [])], default=0) + 1
        mem.setdefault("correos_importantes", []).append({
            "id": nuevo_id, "remitente": categoria_o_curso, "asunto": titulo,
            "resumen": "Pendiente por atender", "vencimiento": vencimiento or "2026-11-28 23:59", "completado": False
        })
        guardar_memoria(mem)
        notificar_refresco_hud()
        return sintetizar_respuesta_unica_contextual(titulo, f"Nuevo correo importante registrado: {titulo}.", False)
    elif "proyecto" in t_low:
        nuevo_id = max([x.get("id", 0) for x in mem.get("proyectos_activos", [])], default=0) + 1
        mem.setdefault("proyectos_activos", []).append({
            "id": nuevo_id, "proyecto": categoria_o_curso, "tarea": titulo,
            "vencimiento": vencimiento or "2026-12-15 23:59", "completado": False
        })
        guardar_memoria(mem)
        notificar_refresco_hud()
        return sintetizar_respuesta_unica_contextual(titulo, f"Nuevo proyecto activo agregado: {titulo}.", False)
    return recordar_dato_o_persona("logro", categoria_o_curso, titulo)


def escanear_contexto_mensajeria_y_web() -> list[str]:
    pistas = []
    if shutil.which("wmctrl"):
        try:
            salida = subprocess.check_output(["wmctrl", "-l"], text=True, stderr=subprocess.DEVNULL)
            for linea in salida.splitlines():
                partes = linea.split(None, 3)
                if len(partes) >= 4:
                    titulo = partes[3].strip()
                    if any(k in titulo.lower() for k in ("whatsapp", "telegram", "discord", "gmail", "chrome", "classroom", "lira", "unam space", "suma", "derecho", "soren", "onshape")):
                        pistas.append(titulo)
        except Exception:
            pass
    return pistas


def auto_aprender_de_interaccion(texto_usuario: str, client_gemini=None, modelo_activo: str = "models/gemini-3.1-flash-lite") -> None:
    texto_norm = _normalizar_texto_comparacion(texto_usuario)
    patrones_completado = (
        "ya hice", "ya entregue", "ya termine", "ya conclui", "complete",
        "acabo de terminar", "ya revise", "ya conteste", "marca como completad", "ya quedo",
    )
    if any(pat in texto_norm for pat in patrones_completado):
        marcar_entregado_o_actualizar_item(texto_usuario)


def obtener_resumen_gmail_hablado(pregunta_usuario: str = "Revisa mis correos importantes") -> str:
    sincronizar_imap_gmail_si_disponible()
    mem = depurar_y_actualizar_todo_el_contexto()
    correos = mem.get("correos_importantes", [])
    if not correos:
        hechos = "Todos los correos importantes ya fueron atendidos o archivados. Su bandeja prioritaria está al día."
    else:
        partes = [f"De {c['remitente']}: {c['asunto']} ({c['resumen']})" for c in correos[:4]]
        hechos = "Correos y avisos recientes por atender en Gmail: " + "; ".join(partes)
    return sintetizar_respuesta_unica_contextual(pregunta_usuario, hechos, incluir_punto_de_vista=True)


def obtener_resumen_classroom_hablado(pregunta_usuario: str = "Revisa mis asignaciones de Classroom") -> str:
    sincronizar_imap_gmail_si_disponible()
    mem = depurar_y_actualizar_todo_el_contexto()
    tareas = mem.get("classroom_asignaciones", [])
    if not tareas:
        hechos = "Excelente noticia: no tiene ninguna asignación pendiente por entregar en Google Classroom."
    else:
        partes = [
            f"{t['titulo']} de {t['curso']} (vence {formatear_fecha_humana_classroom(t['entrega'])})"
            for t in tareas
        ]
        hechos = "Asignaciones vigentes en Google Classroom próximas a entregar: " + "; ".join(partes)
    return sintetizar_respuesta_unica_contextual(pregunta_usuario, hechos, incluir_punto_de_vista=True)


def recordar_dato_o_persona(categoria: str, clave_o_nombre: str, detalle: str) -> str:
    mem = cargar_memoria()
    cat_low = categoria.lower()
    ahora_fecha = datetime.date.today().isoformat()

    if any(k in cat_low for k in ("persona", "quien", "amigo", "pareja", "novia", "profesor", "contacto")):
        k = clave_o_nombre.lower().strip()
        personas = mem.get("personas", {})
        if k in personas:
            personas[k]["relacion"] = detalle
            personas[k].setdefault("notas", []).append(f"[{ahora_fecha}] {detalle}")
        else:
            personas[k] = {
                "nombre": clave_o_nombre.strip().title(),
                "relacion": detalle,
                "notas": [f"Registrado el {ahora_fecha}: {detalle}"]
            }
        mem["personas"] = personas
        guardar_memoria(mem)
        hechos = f"Se guardó en la memoria neuronal sobre {clave_o_nombre.strip().title()}: {detalle}."
        return sintetizar_respuesta_unica_contextual(detalle, hechos, incluir_punto_de_vista=True)

    logros = mem.get("logros_y_hechos_completados", [])
    logros.append({"fecha": ahora_fecha, "hecho": f"{clave_o_nombre}: {detalle}".strip(": ")})
    mem["logros_y_hechos_completados"] = logros
    guardar_memoria(mem)
    hechos = f"Se registró en el historial permanente de logros de Max: {detalle}."
    return sintetizar_respuesta_unica_contextual(detalle, hechos, incluir_punto_de_vista=True)


def consultar_memoria_completa(consulta: str = "") -> str:
    mem = depurar_y_actualizar_todo_el_contexto()
    q = consulta.lower().strip()

    if any(p in q for p in ("pareja", "novia", "soren", "alessa")):
        p_info = mem["personas"]["soren alessa"]
        notas_str = " ".join(p_info.get("notas", []))
        hechos = f"La pareja de Max es {p_info['nombre']}. Relación y perfil: {p_info['relacion']} Notas: {notas_str}"
        return sintetizar_respuesta_unica_contextual(consulta or "¿Quién es Soren Alessa?", hechos, incluir_punto_de_vista=True)

    for k, p_info in mem.get("personas", {}).items():
        if k in q or p_info["nombre"].lower() in q:
            notas_str = " ".join(p_info.get("notas", []))
            hechos = f"Persona consultada: {p_info['nombre']}. Relación con Max: {p_info['relacion']} Notas: {notas_str}"
            return sintetizar_respuesta_unica_contextual(consulta, hechos, incluir_punto_de_vista=True)

    logros = mem.get("logros_y_hechos_completados", [])[-4:]
    logros_txt = "; ".join(f"el {l['fecha']} {l['hecho']}" for l in logros)
    nombres_personas = ", ".join(p["nombre"] for p in mem.get("personas", {}).values())
    hechos = (
        f"La pareja actual de Max es Soren Alessa. Logros recientes completados por Max: {logros_txt}. "
        f"Personas registradas en su círculo: {nombres_personas}."
    )
    return sintetizar_respuesta_unica_contextual(consulta or "¿Qué recuerdas en tu memoria?", hechos, incluir_punto_de_vista=True)


if __name__ == "__main__":
    # Forzar migración y depuración inmediata en disco
    if ARCHIVO_MEMORIA.exists():
        ARCHIVO_MEMORIA.unlink()
    depurar_y_actualizar_todo_el_contexto()
    notificar_refresco_hud("Classroom y Gmail actualizados con las entregas vigentes.")
    print("[OK] Base de datos memoria_jarvis.json actualizada a Mark XVII.")
