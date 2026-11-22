# J.A.R.V.I.S. MARK XIV — Asistente Holográfico de Ingeniería para Ubuntu Linux

![OS](https://img.shields.io/badge/OS-Ubuntu%2024.04%20LTS-E95420?logo=ubuntu&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![AI](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4?logo=google&logoColor=white)
![UI](https://img.shields.io/badge/HUD-PySide6%20%2B%20HTML5%203D-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-00e5ff)

Asistente personal de escritorio impulsado por IA para **Ubuntu Linux (GNOME / Wayland & X11)** inspirado en el J.A.R.V.I.S. de Tony Stark. Combina control por voz en español, desbloqueo por doble palmada, HUD holográfico con telemetría en vivo, proyector 3D interactivo, generación de dossiers científicos con ecuaciones **MathJax 3 + bibliografía IEEE**, visión real de pantalla, grabación de videoclips y autonomía proactiva.

## Características Principales

| Módulo | Capacidades |
| :--- | :--- |
| **Protocolo Showstopper** | Bloquea la estación al encender; con **2 palmadas** desbloquea la sesión, reproduce *Should I Stay or Should I Go* durante 5 s, despliega apps en mosaico y continúa la playlist en aleatorio. |
| **HUD Holográfico (`PySide6`)** | Interfaz translúcida con **Reactor Arc animado**, animaciones de entrada/cierre, modo compacto/mini arrastrable y pantalla completa con 1 clic. Muestra CPU, RAM, batería, GPU NVIDIA, Classroom y Gmail. |
| **Laboratorio 3D Interactivo** | Motor 3D matricial con Z-Buffer propio en HTML5 Canvas. Proyecta modelos en pantalla completa (Motor Jaula de Ardilla, Transformador, Solenoide, Rover 6WD o cualquier objeto generado con Gemini) con Vista Explosiva, corte interno y Rayos X. |
| **Dossiers Científicos** | Investigación técnica profunda con **MathJax 3**, notación Unicode limpia para copiar sin código LaTeX crudo, ejercicios resueltos paso a paso y bibliografía vía API **Crossref / DOI** en formato IEEE. |
| **Visión Real y Seguridad** | Captura nativa vía GNOME Shell D-Bus (`org.gnome.Shell.Screenshot`) para describir software, CAD o código sin alucinaciones, más **Centinela Anti-Intrusos** por webcam. |
| **Autonomía Viva** | Detector de aburrimiento (`Mutter.IdleMonitor`), Curiosidad Visual Espontánea, Modo Madrugada, réplica conversacional sin decir "Jarvis", auto-ahorro de batería y modo silencio para clases. |
| **Spotify, Clips y Hardware** | Control completo de Spotify y canciones por nombre vía MPRIS2, videoclips rápidos (`clipea esto`) en `~/Vídeos/Jarvis_Clips/`, control de brillo/teclado ASUS TUF, escáner Wi-Fi y apagado ACPI limpio. |

## Arquitectura de Archivos

- `jarvis_wake.py`: Núcleo maestro (2 palmadas, audio, Spotify, centinela autónomo y hardware).
- `jarvis_brain.py`: Orquestador cognitivo (Gemini API), visión real de pantalla e interceptores de voz.
- `jarvis_hud.py`: Interfaz holográfica PySide6 (ventana flotante, mini y pantalla completa animada).
- `jarvis_memory.py`: Memoria persistente, auto-depuración por fechas, sync Classroom/Gmail y cero-repetición.
- `jarvis_3d.py`: Proyector CAD 3D holográfico interactivo (HTML5 Canvas Z-Buffer + Gemini 3D).
- `jarvis_dossier.py`: Compilador de dossiers técnicos holográficos (MathJax 3 + API Crossref IEEE).
- `start_jarvis.sh` / `install.sh`: Guardián de arranque automático en GNOME e instalador de 1 comando.

## Instalación Rápida en Ubuntu 24.04

1. Clona el repositorio y entra a la carpeta:
   `git clone https://github.com/MaxGuz1203/jarvis-mark-xiv.git ~/jarvis && cd ~/jarvis`
2. Ejecuta el instalador automático:
   `chmod +x install.sh && ./install.sh`
3. Agrega tu clave de [Google AI Studio](https://aistudio.google.com/) en `~/jarvis/.env`:
   `GEMINI_API_KEY="tu_clave_aqui"` (opcional: `GMAIL_USER` y `GMAIL_APP_PASSWORD`).
4. Recarga la terminal para activar el atajo de voz `jv`:
   `source ~/.bashrc`

## Modos de Ejecución

- `./start_jarvis.sh` — Inicia el protocolo completo (bloquea pantalla y espera 2 palmadas).
- `jv` — Activa escucha directa de 1 comando por voz desde cualquier terminal.
- `~/jarvis/.venv/bin/python ~/jarvis/jarvis_wake.py --hud` — Abre únicamente el HUD holográfico.
- `~/jarvis/.venv/bin/python ~/jarvis/jarvis_wake.py --test-autonomia` — Prueba la curiosidad visual + réplica directa.
- `~/jarvis/.venv/bin/python ~/jarvis/jarvis_wake.py --clip` — Graba un videoclip de 15 s de la pantalla.

## Comandos de Voz Principales

- **Visión:** *"Jarvis, dime qué se muestra en mi pantalla"*, *"mira por la cámara web"*, *"analiza este código"*.
- **Modelos 3D:** *"Jarvis, crea un modelo 3D de un motor de inducción tipo jaula de ardilla"*, *"proyecta en 3D un transformador"*.
- **Investigación:** *"Jarvis, investiga a fondo sobre [tema]"*.
- **Spotify:** *"Jarvis, pon Who's Lovin' You de los Jackson"*, *"cambia de canción"*, *"pausa la música"*.
- **Clips y Apps:** *"Jarvis, clipea esto"*, *"graba mi pantalla"*, *"detén la grabación"*, *"abre Onshape / Canva / LaTeX / VS Code"*, *"pon completas las ventanas"*.
- **Classroom y Memoria:** *"Jarvis, qué tareas tengo en Classroom"*, *"sincroniza mi Classroom"*, *"ya entregué [tarea]"*, *"qué correos tengo"*.
- **Laptop y Silencio:** *"Jarvis, activa el modo ahorro de batería"*, *"pon el brillo al 40%"*, *"apaga la luz del teclado"*, *"entra en modo silencio"*, *"despierta"*, *"apaga la laptop por completo"*.

## Autor

**Luis Maximiliano Guzman Ortiz (Max)** — Ingeniería Eléctrica Electrónica, FI UNAM.
GitHub: [@MaxGuz1203](https://github.com/MaxGuz1203)
