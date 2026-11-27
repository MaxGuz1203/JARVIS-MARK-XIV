#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Fase 2 (v2): Entrenador IDF + Token Dropout para JarvisIntentNet
Uso:
  python entrenar_intent_nn.py --entrenar
  python entrenar_intent_nn.py --probar
  python entrenar_intent_nn.py --agregar <intencion> "<frase>"
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import collections
import json
import math
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

DIRECTORIO_BASE = Path.home() / "jarvis"
if str(DIRECTORIO_BASE) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_BASE))

from jarvis_intent_net import (
    DIR_MODELOS_NN,
    INTENCIONES_JARVIS,
    JarvisIntentNet,
    RUTA_MODELO_INTENT,
    codificar_con_pesos,
    extraer_tokens_ponderados,
    normalizar_texto_intent,
    predecir_intencion_texto,
)

RUTA_DATASET_INTENT = DIRECTORIO_BASE / "dataset_nn" / "intenciones_jarvis.json"

DATASET_BASE_INTENCIONES: dict[str, list[str]] = {
    "conversacion_general": [
        "hola jarvis como estas hoy",
        "buenos dias que tal va todo",
        "explicame que es la ley de faraday",
        "cual es la diferencia entre un motor sincrono y uno de induccion",
        "ayudame a entender como funciona un controlador pid",
        "que opinas de mi idea para el proyecto del rover",
        "cuentame un chiste de ingenieros",
        "como se calcula el deslizamiento de un motor trifasico",
        "dame un consejo para organizar mi tarde de estudio",
        "por que el cielo se ve azul",
        "que hora es ahorita",
        "como resolver una integral por partes",
        "que significa factor de potencia en circuitos de corriente alterna",
        "estoy cansado de programar hoy que recomiendas",
        "traduceme esta frase al ingles",
        "quien fue nikola tesla y que invento",
        "dime tres datos curiosos sobre marte",
        "resumeme el teorema de thevenin facil",
        "que es una red neuronal convolucional",
        "como puedo mejorar mi promedio en la facultad",
        "estamos probando si me entiendes bien",
        "que dia es hoy y que clima hace",
        "dame ideas para un nombre de proyecto de robotica",
        "gracias por tu ayuda de hace rato",
        # Negativos difíciles y plática casual (evitan falsos disparos de herramientas)
        "que es la energia cinetica y potencial en fisica",
        "cuanto cuesta una pantalla oled para laptop",
        "quien invento la musica rock en los cincuenta",
        "que tal estuvo tu dia hoy amigo",
        "tengo mucha hambre que me recomiendas cenar",
        "me duele la cabeza de tanto estudiar calculo",
        "como funciona un router wifi por dentro",
        "por que el rover perseverance usa energia nuclear",
        "cual es la velocidad de la luz en el vacio",
        "dime una frase motivadora para seguir trabajando",
        "que pelicula de ciencia ficcion me recomiendas ver",
        "en que año se fundo la unam en mexico",
        "como se dice buenas noches en japones",
        "cuanto es la raiz cuadrada de doscientos cincuenta y seis",
        "no manches que calor hace hoy en coyoacan",
        "estoy platicando nada mas contigo un rato",
        "explicalo con peras y manzanas por favor",
        "que diferencia hay entre corriente directa y alterna",
        "como funciona el efecto lombard en la voz humana",
        "cual es el mejor lenguaje para aprender robotica",
        "que opinas de la inteligencia artificial moderna",
        "cuantos planetas tiene el sistema solar",
        "dime un dato random de astronomia",
        "ayudame a redactar un mensaje bonito y corto",
    ],
    "musica_reproducir": [
        "pon musica en spotify",
        "reproduce algo bueno para trabajar",
        "pon mi playlist rework ahora",
        "quiero escuchar should i stay or should i go",
        "ponme whos lovin you de los jackson",
        "reanuda la musica por favor",
        "continua reproduciendo spotify",
        "dale play a la musica",
        "pon algo de rock para programar",
        "reproduce la cancion de back in black",
        "ponme musica de fondo para estudiar",
        "vuelve a poner la musica",
        "inicia mi lista de spotify",
        "quiero oir una cancion en spotify",
        "pon la rola de iron man",
        "suena la playlist rework",
        "activa la musica otra vez",
        "reproduce musica aleatoria",
        "ponme algo chido en spotify",
        "sigue con la musica",
        "play a spotify por favor",
        "pon canciones en aleatorio en spotify",
        "quiero escuchar musica mientras programo",
        "reproduce mi musica favorita en spotify",
        "dale play otra vez a mi playlist",
        "ponme una rola de the clash",
        "vuelve a darle play a la musica",
        "arranca la musica de spotify",
    ],
    "musica_control": [
        "pausa la musica",
        "ponle pausa a spotify",
        "deten la musica un momento",
        "para la musica por favor",
        "quita la musica ya",
        "silencia spotify",
        "cambia la cancion",
        "cambia de cancion por otra",
        "pon la siguiente cancion",
        "saltate esta cancion",
        "salta esta rola no me gusta",
        "adelanta a la siguiente pista",
        "pon otra rola diferente",
        "regresa a la cancion anterior",
        "pon la cancion pasada otra vez",
        "vuelve a la pista de atras",
        "cierra spotify completamente",
        "calla la musica tantito",
        "pasale a la que sigue",
        "quita esa rola y pon otra",
        "siguiente pista en spotify",
        "pausar reproduccion de spotify",
        "detener musica ahorita",
        "regresar a la rola anterior",
        "brinca esta cancion por favor",
        "quita esta cancion y pon la siguiente",
        "pausa tantito spotify",
        "cancion anterior por favor",
    ],
    "vision_pantalla": [
        "dime que se muestra en mi pantalla",
        "que ves en mi pantalla ahora mismo",
        "analiza este codigo que tengo abierto",
        "echale un ojo a este error que me salio",
        "mira mi pantalla y dime que falla",
        "revisa lo que estoy programando aqui",
        "lee lo que dice esta ventana",
        "puedes ver que programa tengo abierto",
        "observa mi escritorio y ayudame con esto",
        "fijate en esta ecuacion que esta en pantalla",
        "que error marca la terminal ahorita",
        "ayudame a depurar lo que aparece aqui",
        "describe lo que ves en el monitor",
        "checa mi pantalla por favor",
        "mira este circuito que estoy diseñando",
        "ves algun bug en este codigo",
        "examina la grafica que esta abierta",
        "que dice el texto de mi pantalla",
        "analiza la imagen que tengo enfrente",
        "dime que opinas de lo que tengo abierto",
        "observa el error que sale en la consola",
        "checa este codigo en mi monitor y dime que esta mal",
        "lee mi pantalla y explicame el fallo",
        "mira lo que esta pasando en mi pantalla",
        "puedes leer el error de codigo que tengo aqui",
        "revisa el diagrama que se ve en pantalla",
        "que hay actualmente en mi monitor",
        "analiza lo que aparece en la terminal",
    ],
    "modelo_3d": [
        "proyecta un modelo 3d del motor de induccion",
        "muestrame en 3d un motor jaula de ardilla",
        "abre el holograma de un transformador trifasico",
        "quiero ver un rover en tres dimensiones",
        "genera un modelo tridimensional de un solenoide",
        "muestrame por dentro en 3d como es un generador electrico",
        "proyecta un holograma del brazo robotico",
        "arma una visualizacion 3d de un reactor",
        "crea un modelo 3d de un engrane planetario",
        "enseñame en 3d un circuito magnetico",
        "despliega la maqueta 3d del satelite",
        "quiero rotar y explotar las piezas 3d de un motor",
        "proyecta una figura tridimensional de un dron",
        "abre el proyector holografico con un alternador",
        "muestra un modelo en 3d de una turbina",
        "visualiza en tercera dimension un rotor",
        "hazme un holograma de un transformador",
        "pon el modelo 3d del rover lunar",
        "quiero inspeccionar en 3d un estator",
        "dibuja en 3d un electroiman",
        "lanza el proyector 3d de un motor electrico",
        "holograma interactivo de un piston",
        "proyecta en 3d una bobina de tesla",
        "quiero ver la vista explosiva 3d de un motor",
        "abre un modelo 3d del brazo mecanico",
        "muestra el holograma tridimensional de un cohete",
        "modela en 3d un condensador cilindrico",
        "proyector 3d de un motor sincrono",
    ],
    "dossier_investigacion": [
        "investiga a fondo sobre motores brushless",
        "armame un reporte tecnico completo sobre transformadores",
        "hazme un dossier cientifico de electronica de potencia",
        "genera unos apuntes formales con ecuaciones sobre maxwell",
        "investiga a profundidad mapas de costos en ros 2",
        "prepara un documento tecnico con referencias ieee sobre inversores",
        "compila un dossier de investigacion de control vectorial foc",
        "necesito un estudio completo con formulas de filtros kalman",
        "haz una investigacion detallada sobre celdas de combustible",
        "crea un reporte universitario sobre maquinas electricas rotatorias",
        "busca articulos cientificos y hazme un dossier de lidar",
        "desarrolla un documento de estudio con ejercicios de circuitos rlc",
        "investiga bien el tema de modulacion pwm sinusoidal",
        "arma un informe cientifico sobre navegacion autonoma de rovers",
        "quiero un dossier con bibliografia real sobre semiconductores sic",
        "haz un apunte tecnico con ecuaciones de analisis de fourier",
        "genera una guia tecnica profunda de microcontroladores fpga",
        "prepara un dossier academico sobre sistemas trifasicos",
        "investiga a fondo la teoria de control clasico",
        "creame un documento formal sobre rectificadores controlados",
        "compila un reporte de investigacion con citas sobre baterias lipo",
        "investiga a detalle el funcionamiento de sensores ultrasonicos",
        "genera un dossier completo con formulas de electromagnetismo",
        "armame un informe tecnico con bibliografia ieee de pid",
        "haz una investigacion formal de convertidores buck boost",
        "documento cientifico a fondo sobre cinematica inversa",
        "prepara apuntes universitarios con ecuaciones de maquinas sincronas",
        "investiga a profundidad redes neuronales convolucionales",
    ],
    "classroom_memoria": [
        "revisa mis pendientes de classroom",
        "que tareas tengo por entregar esta semana",
        "sincroniza mi classroom ahora mismo",
        "actualiza mis asignaciones de classroom",
        "revisa mis correos importantes de gmail",
        "tengo algun correo nuevo de mis profesores",
        "ya entregue la practica de maquinas electricas",
        "marca como completada la tarea de electricidad y magnetismo",
        "ya termine el pendiente de etiquetar en labelme",
        "recuerda que el viernes tengo examen parcial",
        "guarda en tu memoria que mi reunion es a las cuatro",
        "que proyectos vigentes tengo en mi memoria",
        "dime mi agenda y tareas pendientes de classroom",
        "borra de mis pendientes la tarea que ya subi",
        "que me falta entregar en classroom",
        "checa si llego algun aviso en gmail",
        "anota en mi memoria este recordatorio importante",
        "que recuerdas sobre mis pendientes del laboratorio",
        "marca como hecho el reporte de servicio social",
        "dime que entregas de tareas se vencen pronto",
        "sincroniza mis correos de gmail y classroom",
        "ya subi mi tarea de maquinas quitala de pendientes",
        "acuerdate que mañana tengo junta de unam space",
        "revisa mi bandeja de gmail por favor",
        "cuales son mis tareas pendientes de la facultad",
        "guarda este pendiente en mi agenda",
        "ya complete la asignacion de laboratorio",
        "checa mis entregas pendientes en classroom",
    ],
    "abrir_apps_ventanas": [
        "abre onshape en el navegador",
        "abre canva y latex en mi estacion de trabajo",
        "lanza visual studio code por favor",
        "abre la terminal y chrome",
        "acomoda todas mis ventanas en mosaico",
        "divide la pantalla con mis aplicaciones",
        "pon esta ventana en pantalla completa",
        "maximiza todas las ventanas abiertas",
        "limpia el escritorio pizarra limpia",
        "cierra todas las ventanas abiertas",
        "cierra todo lo que tengo abierto",
        "fija esta ventana siempre encima",
        "abre whatsapp y gemini",
        "inicia el editor de codigo vs code",
        "organiza mi espacio de trabajo en cuadrantes",
        "ejecuta protocolo de estudio en el escritorio",
        "abre el navegador de internet",
        "quita todas las ventanas del escritorio",
        "ponme mis herramientas de ingenieria abiertas",
        "lanza el programa de diseño cad",
        "abrir onshape y visual studio code",
        "acomoda las ventanas en cuatro cuadrantes",
        "cierra las aplicaciones abiertas ahorita",
        "abre google chrome por favor",
        "maximiza la ventana activa",
        "ordena mis ventanas en mosaico simetrico",
        "abre overleaf y canva en chrome",
        "limpia todas las ventanas con pizarra limpia",
    ],
    "grabacion_clips": [
        "clipea esto ahora mismo",
        "saca un clip de los ultimos quince segundos",
        "guarda lo que acaba de pasar en video",
        "graba mi pantalla por favor",
        "inicia la grabacion de pantalla",
        "deten la grabacion de video",
        "para de grabar la pantalla",
        "guarda una caja negra del sistema",
        "captura un videoclip de lo que estoy haciendo",
        "hazme un clip rapido de la pantalla",
        "empieza a grabar un video del escritorio",
        "termina de grabar el clip",
        "salva los ultimos segundos en un video",
        "activa la caja negra ahora",
        "graba esta demostracion en pantalla",
        "corta la grabacion de video",
        "guarda este momento en clip",
        "saca una grabacion corta de esto",
        "registra un clip de lo que se ve",
        "deten el video que estas grabando",
        "clipea los ultimos segundos por favor",
        "comienza a grabar la pantalla en video",
        "frena la grabacion de pantalla",
        "guarda un videoclip de esto",
        "graba un clip rapido del escritorio",
        "activa grabacion de caja negra",
        "para el video que estas grabando",
        "saca un videoclip de los ultimos 15 segundos",
    ],
    "hardware_energia": [
        "activa el modo ahorro de bateria",
        "se me esta acabando la pila ahorra bateria",
        "pon la laptop en modo turbo maximo rendimiento",
        "dime el estado del sistema y temperatura",
        "cuanta bateria y memoria ram me quedan",
        "como anda el uso de cpu y gpu ahorita",
        "sube el brillo de la pantalla",
        "baja el brillo que me lastima los ojos",
        "apaga la luz del teclado",
        "prende la iluminacion del teclado",
        "cambia el perfil de los ventiladores",
        "cuantos grados tiene mi tarjeta grafica",
        "pon el modo balanceado de energia",
        "revisa el consumo de recursos de mi laptop",
        "baja la intensidad de las luces del teclado",
        "dime la telemetria completa del equipo",
        "haz que la bateria dure mas tiempo",
        "sube el brillo al maximo",
        "checa si se esta calentando la computadora",
        "pon energia en ahorro para que aguante la pila",
        "se me muere la pila activa ahorro",
        "cuanta carga de bateria tiene la laptop",
        "temperatura de la cpu y la rtx ahorita",
        "apaga los leds rgb del teclado",
        "enciende el brillo del teclado",
        "cambia a modo ahorro de energia",
        "modo rendimiento turbo en los ventiladores",
        "dime porcentaje de cpu ram y bateria",
    ],
    "modo_silencio": [
        "activa el modo silencio",
        "no me molestes voy a entrar a clase",
        "silenciate estoy en clase de suma",
        "guarda silencio hasta que te vuelva a hablar",
        "pon modo no molestar por favor",
        "callate un rato que estoy en reunion",
        "despierta del modo silencio",
        "vuelve en linea ya termine la clase",
        "sal del modo silencio jarvis",
        "reactivate ya puedes hablar normal",
        "voy a dar asesoria no hables nada",
        "pausa tus comentarios autonomos por ahora",
        "silencio total durante la junta",
        "ya acabe mi clase vuelve a activarte",
        "modo silencio activado",
        "no interrumpas en un buen rato",
        "puedes volver a hablar ya sali de clase",
        "apaga las respuestas espontaneas",
        "desactiva el modo silencio",
        "estoy en examen quedate callado",
        "pon silencio porque voy a dar clase",
        "no digas nada hasta que te avise",
        "ya termine de dar clase despierta",
        "quita el modo no molestar",
        "entra en modo silencio por favor",
        "silencia tus alertas estoy en junta",
        "reactivate jarvis ya acabo la reunion",
        "quedate en silencio un buen rato",
    ],
    "seguridad_red": [
        "vigila mi laptop por intrusos",
        "activa el centinela anti intrusos",
        "quien esta conectado en mi red wifi",
        "escanea los dispositivos de mi red local",
        "activa el modo sigilo ahora",
        "revisa si hay intrusos cerca de la camara",
        "protege mi estacion mientras me paro",
        "checa que equipos estan en el wifi",
        "pon vigilancia con la camara web",
        "muestrame las ips conectadas a mi router",
        "asegura la laptop en modo sigilo",
        "detecta si alguien toca mi computadora",
        "haz un escaneo de seguridad de red",
        "cuantos dispositivos hay en mi internet",
        "activa alerta de intrusos",
        "revisa la seguridad de mi conexion wifi",
        "vigila el cuarto con la camara",
        "alguien desconocido esta en mi wifi",
        "inicia protocolo de vigilancia",
        "verifica los aparatos en mi red",
        "escanea quien se colgo de mi wifi",
        "cuida mi laptop por si llega un intruso",
        "activa vigilancia de camara anti intrusos",
        "lista los equipos conectados a mi red",
        "pon modo sigilo y vigila el equipo",
        "revisa las direcciones ip de mi red",
        "vigilancia activa contra intrusos",
        "quienes estan usando mi red local",
    ],
    "apagar_sistema": [
        "apaga la laptop ahora",
        "apaga el sistema completamente",
        "apaga la computadora por favor",
        "ya estuvo por hoy apaga todo",
        "buenas noches apaga la laptop",
        "inicia secuencia de apagado total",
        "cierra todo y apaga el equipo",
        "duerme y apaga la compu",
        "terminamos por hoy apaga la maquina",
        "desconecta todo y apaga ubuntu",
        "apagate ya me voy a dormir",
        "ejecuta el apagado definitivo del sistema",
        "corta corriente y apaga la laptop",
        "apagar computadora ahora mismo",
        "ya termine de trabajar apaga todo",
        "hasta mañana apaga el sistema",
        "mandala a apagar por completo",
        "quiero apagar mi laptop",
        "procede a apagar el equipo",
        "apaga la pc por completo",
        "apaga mi equipo ya me voy",
        "secuencia de apagado definitivo ahora",
        "apagar sistema operativo ubuntu",
        "ya acabe apaga la computadora",
        "apaga esta laptop por favor",
        "apagado total del sistema ahora",
        "desconecta y apaga la maquina",
        "apaga la laptop buenas noches",
    ],
}

MULETILLAS_INICIO = ["", "", "", "jarvis", "oye jarvis", "por favor", "oye", "hey jarvis"]
MULETILLAS_FIN = ["", "", "", "por favor", "ahora mismo", "ahorita", "jarvis", "porfa"]


def asegurar_dataset_en_disco() -> dict[str, list[str]]:
    RUTA_DATASET_INTENT.parent.mkdir(parents=True, exist_ok=True)
    if RUTA_DATASET_INTENT.exists():
        actual = json.loads(RUTA_DATASET_INTENT.read_text(encoding="utf-8"))
        for intent, frases in DATASET_BASE_INTENCIONES.items():
            existentes = list(actual.get(intent, []))
            norm_set = {normalizar_texto_intent(x) for x in existentes}
            for f in frases:
                if normalizar_texto_intent(f) not in norm_set:
                    existentes.append(f)
                    norm_set.add(normalizar_texto_intent(f))
            actual[intent] = existentes
    else:
        actual = {k: list(v) for k, v in DATASET_BASE_INTENCIONES.items()}

    RUTA_DATASET_INTENT.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
    return actual


def agregar_frase_a_dataset(intencion: str, frase: str) -> None:
    if intencion not in INTENCIONES_JARVIS:
        print(f"[!] Intención desconocida: '{intencion}'. Válidas:\n  " + ", ".join(INTENCIONES_JARVIS))
        return
    datos = asegurar_dataset_en_disco()
    datos.setdefault(intencion, []).append(frase.strip())
    RUTA_DATASET_INTENT.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Frase agregada a '{intencion}': \"{frase}\"")
    print("     Ahora ejecuta: python entrenar_intent_nn.py --entrenar")


def _aumentar_frase_es(texto: str) -> str:
    palabras = normalizar_texto_intent(texto).split()
    if not palabras:
        return texto
    if len(palabras) >= 5 and random.random() < 0.30:
        palabras.pop(random.randrange(len(palabras)))
    pref = random.choice(MULETILLAS_INICIO)
    suf = random.choice(MULETILLAS_FIN)
    return " ".join([x for x in [pref, " ".join(palabras), suf] if x]).strip()


class DatasetIntencionesIDF(Dataset):
    def __init__(self, pares, vocab, idf_map, entrenar=True, factor_aug=5):
        self.pares = pares
        self.vocab = vocab
        self.idf_map = idf_map
        self.entrenar = entrenar
        self.factor_aug = factor_aug if entrenar else 1

    def __len__(self) -> int:
        return len(self.pares) * self.factor_aug

    def __getitem__(self, idx: int):
        txt, y = self.pares[idx % len(self.pares)]
        if self.entrenar and random.random() < 0.65:
            txt = _aumentar_frase_es(txt)
        ids, pesos, _ = codificar_con_pesos(txt, self.vocab, self.idf_map)

        # Token Dropout (30%) durante entrenamiento: fuerza a aprender múltiples pistas y evita memorización
        if self.entrenar and len(ids) >= 4:
            pares_ok = [(i, w) for i, w in zip(ids, pesos) if random.random() > 0.30]
            if pares_ok:
                ids = [i for i, _ in pares_ok]
                pesos = [w for _, w in pares_ok]
                s = sum(pesos)
                pesos = [w / s for w in pesos]
        return ids, pesos, y


def _collate_idf(batch):
    indices_list, weights_list, offsets, labels = [], [], [], []
    pos = 0
    for ids, pesos, y in batch:
        offsets.append(pos)
        indices_list.extend(ids)
        weights_list.extend(pesos)
        pos += len(ids)
        labels.append(y)
    return (
        torch.tensor(indices_list, dtype=torch.long),
        torch.tensor(offsets, dtype=torch.long),
        torch.tensor(weights_list, dtype=torch.float32),
        torch.tensor(labels, dtype=torch.long),
    )


def entrenar_intent_net(epocas: int = 55) -> None:
    print("\n============================================================")
    print("  ENTRENAMIENTO FASE 2 (v2) — JarvisIntentNet IDF + OOD")
    print("============================================================")
    datos = asegurar_dataset_en_disco()

    rng = random.Random(42)
    train_items, val_items = [], []
    for idx_c, nombre_c in enumerate(INTENCIONES_JARVIS):
        frases = list(datos.get(nombre_c, []))
        rng.shuffle(frases)
        n_val = max(4, int(round(len(frases) * 0.20)))
        for f in frases[:n_val]:
            val_items.append((f, idx_c))
        for f in frases[n_val:]:
            train_items.append((f, idx_c))
        print(f"  [{idx_c:02d}] {nombre_c:<22}: {len(frases):2d} frases (Train {len(frases)-n_val} | Val {n_val})")

    # Construir vocabulario y pesos IDF SOLO sobre el conjunto de entrenamiento (cero fuga de datos)
    df = collections.Counter()
    for txt, _ in train_items:
        pares_tok, _ = extraer_tokens_ponderados(txt)
        for tok in {t for t, _ in pares_tok}:
            df[tok] += 1

    n_docs = len(train_items)
    vocab = {"<PAD>": 0, "<UNK>": 1}
    idf_map = {"<PAD>": 0.0, "<UNK>": 0.5}
    for tok, doc_freq in df.most_common():
        # Conservar todas las palabras reales; bigramas y char 4-grams solo si aparecen >= 2 veces
        if tok.startswith("w:") or doc_freq >= 2:
            vocab[tok] = len(vocab)
            idf_map[tok] = round(math.log((1.0 + n_docs) / (1.0 + doc_freq)) + 1.0, 4)

    ds_train = DatasetIntencionesIDF(train_items, vocab, idf_map, entrenar=True, factor_aug=5)
    ds_val = DatasetIntencionesIDF(val_items, vocab, idf_map, entrenar=False, factor_aug=1)
    dl_train = DataLoader(ds_train, batch_size=32, shuffle=True, collate_fn=_collate_idf)
    dl_val = DataLoader(ds_val, batch_size=32, shuffle=False, collate_fn=_collate_idf)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDispositivo: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"Vocabulario IDF: {len(vocab):,} tokens | Train: {len(train_items)} ({len(ds_train)}/época) | Val: {len(val_items)}\n")

    modelo = JarvisIntentNet(vocab_size=len(vocab), num_clases=len(INTENCIONES_JARVIS), embed_dim=48, hidden_dim=64).to(device)
    criterio = nn.CrossEntropyLoss(label_smoothing=0.08)
    opt = torch.optim.AdamW(modelo.parameters(), lr=4.5e-3, weight_decay=2.5e-2)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epocas)

    mejor_acc, mejor_loss, mejor_estado = -1.0, 999.0, None
    t0 = time.time()

    for ep in range(1, epocas + 1):
        modelo.train()
        l_tr, ok_tr, tot_tr = 0.0, 0, 0
        for idx_b, off_b, w_b, y_b in dl_train:
            idx_b, off_b, w_b, y_b = idx_b.to(device), off_b.to(device), w_b.to(device), y_b.to(device)
            opt.zero_grad(set_to_none=True)
            out = modelo(idx_b, off_b, w_b)
            loss = criterio(out, y_b)
            loss.backward()
            opt.step()
            l_tr += loss.item() * len(y_b)
            ok_tr += int((out.argmax(dim=1) == y_b).sum().item())
            tot_tr += len(y_b)
        sched.step()

        modelo.eval()
        l_v, ok_v, tot_v = 0.0, 0, 0
        with torch.no_grad():
            for idx_b, off_b, w_b, y_b in dl_val:
                idx_b, off_b, w_b, y_b = idx_b.to(device), off_b.to(device), w_b.to(device), y_b.to(device)
                out = modelo(idx_b, off_b, w_b)
                loss = criterio(out, y_b)
                l_v += loss.item() * len(y_b)
                ok_v += int((out.argmax(dim=1) == y_b).sum().item())
                tot_v += len(y_b)

        val_acc = ok_v / max(1, tot_v)
        val_loss = l_v / max(1, tot_v)
        if val_acc > mejor_acc or (val_acc == mejor_acc and val_loss < mejor_loss):
            mejor_acc, mejor_loss = val_acc, val_loss
            mejor_estado = {k: v.detach().cpu().clone() for k, v in modelo.state_dict().items()}

        if ep == 1 or ep % 5 == 0 or ep == epocas:
            print(f"  Época {ep:02d}/{epocas} | Train Loss: {l_tr/tot_tr:.4f} Acc: {ok_tr/tot_tr*100:5.1f}% | Val Loss: {val_loss:.4f} Acc: {val_acc*100:5.1f}%")

    modelo.load_state_dict(mejor_estado)
    modelo.eval()
    errores = []
    with torch.no_grad():
        for txt, y_real in val_items:
            ids, pesos, _ = codificar_con_pesos(txt, vocab, idf_map)
            out = modelo(
                torch.tensor(ids, dtype=torch.long, device=device),
                torch.tensor([0], dtype=torch.long, device=device),
                torch.tensor(pesos, dtype=torch.float32, device=device),
            )
            probs = torch.softmax(out, dim=-1)[0]
            y_pred = int(probs.argmax().item())
            if y_pred != y_real:
                errores.append((txt, INTENCIONES_JARVIS[y_real], INTENCIONES_JARVIS[y_pred], float(probs[y_pred])))

    DIR_MODELOS_NN.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": mejor_estado,
            "vocab": vocab,
            "idf_map": idf_map,
            "clases": list(INTENCIONES_JARVIS),
            "embed_dim": 48,
            "hidden_dim": 64,
            "val_acc": float(mejor_acc),
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "arquitectura": "JarvisIntentNet_v2_IDF",
        },
        RUTA_MODELO_INTENT,
    )

    if errores:
        print(f"\n--- Detalle de confusiones en validación ({len(errores)}/{len(val_items)}) ---")
        for txt, real, pred, p in errores:
            print(f"  '{txt}' -> Real: {real} | Pred: {pred} ({p*100:.1f}%)")
    else:
        print("\n--- Validación perfecta: 0 errores ---")

    print(f"\n[OK] Modelo v2 guardado en {RUTA_MODELO_INTENT}")
    print(f"     Mejor Val Accuracy: {mejor_acc*100:.1f}% | Tiempo total: {time.time() - t0:.1f}s\n")


def probar_interactivo() -> None:
    if not RUTA_MODELO_INTENT.exists():
        print("[!] Primero entrena el modelo con: python entrenar_intent_nn.py --entrenar")
        return
    print("\n============================================================")
    print("  CONSOLA EN VIVO — JarvisIntentNet v2 (escribe 'salir')")
    print("============================================================")
    print("Prueba tanto comandos naturales como frases random/groserías (deben ir a CONVERSACION_GENERAL):\n")
    while True:
        try:
            frase = input("Tú > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not frase or frase.lower() in ("salir", "exit", "quit"):
            break
        res = predecir_intencion_texto(frase)
        if res:
            top3_str = " | ".join(f"{c}:{p*100:.1f}%" for c, p in res["top3"])
            print(
                f"  [{res['dispositivo'].upper()} {res['latencia_ms']:.2f}ms | vocab={int(res.get('ood_ratio',1)*100)}%] "
                f"-> {res['intencion'].upper()} (conf={res['confianza']*100:.1f}%, margen={res['margen']*100:.1f}%)"
            )
            print(f"  Top-3: {top3_str}\n")


if __name__ == "__main__":
    if "--entrenar" in sys.argv:
        entrenar_intent_net()
    elif "--probar" in sys.argv:
        probar_interactivo()
    elif "--agregar" in sys.argv:
        idx = sys.argv.index("--agregar")
        if idx + 2 < len(sys.argv):
            agregar_frase_a_dataset(sys.argv[idx + 1], " ".join(sys.argv[idx + 2 :]))
        else:
            print('Uso: python entrenar_intent_nn.py --agregar <intencion> "<frase>"')
    else:
        print("Uso: python entrenar_intent_nn.py [--entrenar | --probar | --agregar <intencion> \"<frase>\"]")
