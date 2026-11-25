#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Motor de Biometría Vocal v4 (Anti-Música y Multi-Voz)
- Sustracción espectral adaptativa + filtrado armónico vocal (HNR).
- Evaluación por ventanas deslizantes (aisla la voz de Max aunque haya música o voces de fondo).
- Scoring híbrido: Similitud Coseno + Mahalanobis (pondera formantes propios del hablante).
- Calibración dual: muestras en silencio + muestras con música a alto volumen (efecto Lombard).
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import io
import json
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_PERFIL_VOZ = DIRECTORIO_BASE / "voz_max.json"
SAMPLE_RATE_DEFAULT = 16000
VERSION_PERFIL = 4


def _hz_a_mel(hz: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(hz, dtype=np.float64) / 700.0)


def _mel_a_hz(mel: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (10.0 ** (np.asarray(mel, dtype=np.float64) / 2595.0) - 1.0)


def _banco_filtros_mel(sr: int, n_fft: int = 512, n_mels: int = 26) -> np.ndarray:
    f_min = 100.0
    f_max = min(4500.0, sr / 2.0)
    mels = np.linspace(_hz_a_mel(f_min), _hz_a_mel(f_max), n_mels + 2)
    hz = _mel_a_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    n_bins = n_fft // 2 + 1
    fb = np.zeros((n_mels, n_bins), dtype=np.float64)

    for m in range(1, n_mels + 1):
        b_izq, b_cen, b_der = bins[m - 1], bins[m], bins[m + 1]
        if b_cen > b_izq:
            for k in range(b_izq, min(b_cen, n_bins)):
                fb[m - 1, k] = (k - b_izq) / float(b_cen - b_izq)
        if b_der > b_cen:
            for k in range(b_cen, min(b_der, n_bins)):
                fb[m - 1, k] = (b_der - k) / float(b_der - b_cen)
    return fb


def _matriz_dct(n_mfcc: int = 17, n_mels: int = 26) -> np.ndarray:
    k = np.arange(n_mfcc)[:, None]
    n = np.arange(n_mels)[None, :]
    return np.cos(np.pi * k * (n + 0.5) / float(n_mels)) * np.sqrt(2.0 / float(n_mels))


def _analizar_armonicidad_y_f0(frames_crudos: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (hnr_peak, f0_hz) por cada frame para distinguir voz armónica de ruido/percusión."""
    n = len(frames_crudos)
    hnr = np.zeros(n, dtype=np.float64)
    f0 = np.zeros(n, dtype=np.float64)

    min_lag = max(1, int(sr / 360.0))
    max_lag = min(frames_crudos.shape[1] - 1, int(sr / 75.0))
    if max_lag <= min_lag:
        return hnr, f0

    for i, fr in enumerate(frames_crudos):
        x = fr - np.mean(fr)
        energia = float(np.dot(x, x))
        if energia < 1e-6:
            continue
        corr = np.correlate(x, x, mode="full")[len(x) - 1:]
        corr = corr / (corr[0] + 1e-10)
        ventana = corr[min_lag:max_lag]
        if len(ventana) == 0:
            continue
        idx = int(np.argmax(ventana))
        pico = float(ventana[idx])
        hnr[i] = pico
        if pico > 0.34:
            f0[i] = sr / float(min_lag + idx)

    return hnr, f0


def _vector_desde_segmento(c_seg: np.ndarray, d_seg: np.ndarray) -> np.ndarray | None:
    if len(c_seg) < 4:
        return None
    vec = np.concatenate([
        np.mean(c_seg, axis=0),
        0.28 * np.std(c_seg, axis=0),
        0.24 * np.mean(np.abs(d_seg), axis=0),
    ])
    norma = float(np.linalg.norm(vec))
    if norma < 1e-8 or not np.all(np.isfinite(vec)):
        return None
    return vec / norma


def extraer_firma_vocal(wav_bytes: bytes) -> dict | None:
    """
    Extrae el vector global y los sub-vectores de ventanas deslizantes (48 dims c/u),
    aplicando sustracción espectral, filtrado armónico y estimación automática de SNR.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sr = wf.getframerate()
            n_canales = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
    except Exception:
        return None

    sig = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if n_canales > 1:
        sig = sig.reshape(-1, n_canales).mean(axis=1)
    sig = sig - np.mean(sig)

    frame_len = int(sr * 0.025)
    hop_len = int(sr * 0.010)
    if len(sig) < frame_len * 10:
        return None

    n_frames = 1 + (len(sig) - frame_len) // hop_len
    frames_crudos = np.array([sig[i * hop_len : i * hop_len + frame_len] for i in range(n_frames)])
    rms = np.sqrt(np.mean(frames_crudos ** 2, axis=1))

    # Estimar relación señal-ruido (SNR) del propio clip
    p92 = float(np.percentile(rms, 92))
    p15 = max(1e-5, float(np.percentile(rms, 15)))
    snr_db = float(20.0 * np.log10((p92 + 1e-6) / p15))

    # Filtrado armónico + energía para ignorar silencios, golpes y música percusiva
    hnr, f0_todos = _analizar_armonicidad_y_f0(frames_crudos, sr)
    umbral_rms = max(0.011, p92 * 0.28)
    mascara = (rms >= umbral_rms) & (hnr >= 0.34)

    if int(np.sum(mascara)) < 18:
        puntaje_frame = rms * (0.45 + np.maximum(0.0, hnr))
        top_n = max(14, min(n_frames, int(n_frames * 0.32)))
        top_idx = np.argsort(puntaje_frame)[-top_n:]
        mascara = np.zeros(n_frames, dtype=bool)
        mascara[top_idx] = True

    # Pre-énfasis + Sustracción Espectral Adaptativa sobre toda la pista
    sig_emph = np.append(sig[0], sig[1:] - 0.97 * sig[:-1])
    frames_emph = np.array([sig_emph[i * hop_len : i * hop_len + frame_len] for i in range(n_frames)])

    n_fft = 512
    ventana = np.hamming(frame_len)[None, :]
    espectro = np.abs(np.fft.rfft(frames_emph * ventana, n=n_fft))
    potencia = (espectro ** 2) / float(n_fft)

    # Estimar piso estacionario de ruido/música desde el 15% de frames menos energéticos
    piso_ruido = np.percentile(potencia, 15, axis=0)
    potencia_limpia = np.maximum(potencia - 0.85 * piso_ruido[None, :], 0.10 * potencia)

    fb = _banco_filtros_mel(sr, n_fft=n_fft, n_mels=26)
    log_mel = np.log(np.maximum(np.dot(potencia_limpia[mascara], fb.T), 1e-10))
    dct = _matriz_dct(n_mfcc=17, n_mels=26)
    mfccs = np.dot(log_mel, dct.T)

    c = mfccs[:, 1:17]
    d = np.gradient(c, axis=0) if len(c) >= 3 else np.zeros_like(c)
    f0_activos = f0_todos[mascara]

    vec_global = _vector_desde_segmento(c, d)
    if vec_global is None:
        return None

    f0_validos = f0_activos[f0_activos > 0]
    f0_global = float(np.median(f0_validos)) if len(f0_validos) >= 3 else 0.0

    # Ventanas deslizantes (~0.45s de voz pura c/u) para resistir voces ajenas o cortes de música
    ventanas = []
    win_len = 40
    step = 12
    if len(c) > win_len + 6:
        for start in range(0, len(c) - win_len + 1, step):
            v_w = _vector_desde_segmento(c[start : start + win_len], d[start : start + win_len])
            if v_w is not None:
                f_w = f0_activos[start : start + win_len]
                f_w_val = f_w[f_w > 0]
                f0_w = float(np.median(f_w_val)) if len(f_w_val) >= 3 else f0_global
                ventanas.append({"vector": v_w.tolist(), "f0": round(f0_w, 2)})
    else:
        ventanas.append({"vector": vec_global.tolist(), "f0": round(f0_global, 2)})

    return {
        "vector": vec_global.tolist(),
        "ventanas": ventanas,
        "f0": round(f0_global, 2),
        "snr_db": round(snr_db, 1),
        "frames_activos": int(len(c)),
    }


def _puntuar_vector(
    vec: np.ndarray,
    f0_val: float,
    centroides: list[np.ndarray],
    muestras: list[np.ndarray],
    mu_16: np.ndarray,
    sigma_16: np.ndarray,
    f0_ref: float,
    f0_tol: float,
    entorno_ruidoso: bool,
) -> float:
    sim_cent = max(float(np.dot(vec, c)) for c in centroides)
    sim_max_m = max(float(np.dot(vec, m)) for m in muestras)
    sim_cos = 0.45 * sim_cent + 0.55 * sim_max_m

    # Similitud tipo Mahalanobis sobre los 16 formantes estables del tracto vocal
    z = float(np.sqrt(np.mean(((vec[:16] - mu_16) / (sigma_16 + 0.048)) ** 2)))
    sim_mahal = float(np.exp(-0.18 * (z ** 2)))

    score = 0.65 * sim_cos + 0.35 * sim_mahal

    # Penalización suave por tono F0 (en silencio más estricta; con música/ruido se relaja)
    if f0_val > 0.0 and f0_ref > 0.0:
        diff_f0 = abs(f0_val - f0_ref)
        tol_ef = f0_tol + (22.0 if entorno_ruidoso else 0.0)
        if diff_f0 > tol_ef:
            max_pen = 0.06 if entorno_ruidoso else 0.16
            score -= min(max_pen, ((diff_f0 - tol_ef) / 115.0) * max_pen)

    return max(0.0, min(1.0, score))


def verificar_hablante(wav_bytes: bytes, musica_activa: bool = False) -> tuple[bool, float, str]:
    if not ARCHIVO_PERFIL_VOZ.exists():
        return True, 1.0, "Sin perfil vocal (ejecute --enroll)"

    try:
        perfil = json.loads(ARCHIVO_PERFIL_VOZ.read_text(encoding="utf-8"))
        if perfil.get("version", 1) != VERSION_PERFIL:
            return True, 1.0, "Perfil anterior; ejecute --enroll para calibrar v4"

        centroides = [np.asarray(perfil["centroide_global"], dtype=np.float64)]
        if "centroide_limpio" in perfil:
            centroides.append(np.asarray(perfil["centroide_limpio"], dtype=np.float64))
        if "centroide_ruido" in perfil and perfil["centroide_ruido"]:
            centroides.append(np.asarray(perfil["centroide_ruido"], dtype=np.float64))

        muestras = [np.asarray(v, dtype=np.float64) for v in perfil["vectores"]]
        mu_16 = np.asarray(perfil["mu_16"], dtype=np.float64)
        sigma_16 = np.asarray(perfil["sigma_16"], dtype=np.float64)
        f0_ref = float(perfil.get("f0_mediana", 0.0))
        f0_tol = max(52.0, float(perfil.get("f0_tolerancia", 52.0)))
        umbral_limpio = float(perfil.get("umbral", 0.76))
        umbral_ruido = float(perfil.get("umbral_ruido", max(0.64, umbral_limpio - 0.10)))
    except Exception:
        return True, 1.0, "Error leyendo perfil vocal"

    firma = extraer_firma_vocal(wav_bytes)
    if not firma:
        return True, 0.78, "Audio insuficiente para rechazar"

    snr_db = float(firma.get("snr_db", 15.0))
    entorno_ruidoso = bool(musica_activa or snr_db < 11.5)

    vec_g = np.asarray(firma["vector"], dtype=np.float64)
    score_global = _puntuar_vector(
        vec_g, float(firma.get("f0", 0.0)), centroides, muestras, mu_16, sigma_16, f0_ref, f0_tol, entorno_ruidoso
    )

    scores_win = []
    for w in firma.get("ventanas", []):
        v_w = np.asarray(w["vector"], dtype=np.float64)
        scores_win.append(
            _puntuar_vector(v_w, float(w.get("f0", 0.0)), centroides, muestras, mu_16, sigma_16, f0_ref, f0_tol, entorno_ruidoso)
        )

    if scores_win:
        scores_ord = sorted(scores_win, reverse=True)
        k_top = max(1, min(4, int(np.ceil(len(scores_ord) * 0.35))))
        score_top_win = float(np.mean(scores_ord[:k_top]))
        # Si Max habló sobre voces de fondo o música, las mejores ventanas rescatan su identidad
        score_final = max(score_global, 0.75 * score_top_win + 0.25 * score_global)
    else:
        score_top_win = score_global
        score_final = score_global

    umbral_ef = umbral_ruido if entorno_ruidoso else umbral_limpio
    es_max = score_final >= umbral_ef

    detalle = (
        f"Score={score_final:.3f} (Umbral={umbral_ef:.3f} | Ruido/Mus={'SI' if entorno_ruidoso else 'NO'} "
        f"| SNR={snr_db:.1f}dB | Global={score_global:.3f} | TopWin={score_top_win:.3f} "
        f"| F0={firma.get('f0', 0):.0f}Hz)"
    )
    return es_max, score_final, detalle


def _grabar_muestra_wav(segundos: float = 3.5, sr: int = SAMPLE_RATE_DEFAULT) -> bytes:
    n_samples = int(sr * segundos)
    audio = sd.rec(n_samples, samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    int16_data = np.clip(audio.flatten() * 32767.0, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data.tobytes())
    return buf.getvalue()


def _spotify_jugando_ahora() -> bool:
    if not shutil.which("playerctl"):
        return False
    try:
        st = subprocess.check_output(["playerctl", "--player=spotify", "status"], text=True, stderr=subprocess.DEVNULL).strip().lower()
        return st == "playing"
    except Exception:
        return False


def _capturar_bloque(frases: list[tuple[str, float]], etiqueta: str) -> tuple[list[np.ndarray], list[float]]:
    vectores, f0s = [], []
    for i, (frase, dur) in enumerate(frases, start=1):
        while True:
            input(f"[{etiqueta} {i}/{len(frases)}] Presiona ENTER y di:\n  » \"{frase}\"\n")
            print(f"  🔴 Grabando ({dur}s)...")
            wav_b = _grabar_muestra_wav(dur)
            firma = extraer_firma_vocal(wav_b)
            if firma and firma["frames_activos"] >= 18:
                vectores.append(np.asarray(firma["vector"], dtype=np.float64))
                if firma["f0"] > 0:
                    f0s.append(firma["f0"])
                print(f"  [OK] Capturada (Tono: {firma['f0']:.1f} Hz | SNR: {firma['snr_db']} dB | Frames: {firma['frames_activos']})\n")
                break
            print("  [!] Voz demasiado baja. Repite hablando claro hacia la laptop.\n")
    return vectores, f0s


def entrenar_perfil_vocal_max() -> None:
    frases_limpias = [
        ("Jarvis, pausa la música.", 2.8),
        ("Jarvis, cambia de canción.", 2.8),
        ("Jarvis, dime qué se muestra en mi pantalla.", 3.5),
        ("Jarvis, abre Onshape, Canva y LaTeX ahora mismo.", 3.8),
        ("Jarvis, proyecta un modelo tres D del motor jaula de ardilla.", 4.2),
        ("Jarvis, revisa mis pendientes de Classroom y activa modo ahorro.", 4.2),
    ]
    frases_musica = [
        ("Jarvis, baja el volumen o cambia la canción.", 3.2),
        ("Jarvis, pausa Spotify ahora mismo.", 3.0),
        ("Jarvis, pon Who's Lovin' You de los Jackson.", 3.5),
        ("Jarvis, dime la hora y el estado de mi laptop.", 3.5),
    ]

    print("\n============================================================")
    print("  CALIBRACIÓN BIOMÉTRICA DUAL v4 (SILENCIO + MÚSICA ALTA)")
    print("============================================================")
    print("FASE 1/2: En silencio (pausando Spotify un momento)...\n")
    subprocess.run(["playerctl", "--player=spotify", "pause"], stderr=subprocess.DEVNULL, check=False)

    vecs_limpios, f0s_limpios = _capturar_bloque(frases_limpias, "SILENCIO")

    print("\n------------------------------------------------------------")
    print("FASE 2/2: CON MÚSICA A TODO VOLUMEN (captura efecto Lombard)")
    print("Pon música fuerte en Spotify (o desde tu celular) y habla normal sobre ella.")
    resp_f2 = input("Presiona ENTER para iniciar Fase 2 con Spotify sonando (o escribe 'no' para omitir): ").strip().lower()

    vecs_ruido, f0s_ruido = [], []
    if resp_f2 != "no":
        subprocess.run(["playerctl", "--player=spotify", "play"], stderr=subprocess.DEVNULL, check=False)
        time.sleep(1.0)
        vecs_ruido, f0s_ruido = _capturar_bloque(frases_musica, "MÚSICA")
        subprocess.run(["playerctl", "--player=spotify", "pause"], stderr=subprocess.DEVNULL, check=False)

    todos_vecs = vecs_limpios + vecs_ruido
    todos_f0 = f0s_limpios + f0s_ruido

    def _centroide(lista: list[np.ndarray]) -> np.ndarray:
        c = np.mean(np.vstack(lista), axis=0)
        return c / np.linalg.norm(c)

    c_limpio = _centroide(vecs_limpios)
    c_ruido = _centroide(vecs_ruido) if vecs_ruido else None
    c_global = _centroide(todos_vecs)

    matriz = np.vstack(todos_vecs)
    mu_16 = np.mean(matriz[:, :16], axis=0)
    sigma_16 = np.std(matriz[:, :16], axis=0)

    f0_mediana = round(float(np.median(f0s_limpios or todos_f0)), 2) if (f0s_limpios or todos_f0) else 0.0
    f0_tol = round(max(52.0, float(np.std(todos_f0)) * 2.5), 2) if len(todos_f0) >= 2 else 52.0

    # Auto-calibración leave-one-out separada para silencio y ruido
    sims_limp = []
    for i, v in enumerate(vecs_limpios):
        otros = [vecs_limpios[j] for j in range(len(vecs_limpios)) if j != i]
        c_o = _centroide(otros)
        s = _puntuar_vector(v, f0_mediana, [c_o], otros, mu_16, sigma_16, f0_mediana, f0_tol, False)
        sims_limp.append(s)

    umbral_limpio = round(max(0.71, min(0.83, float(min(sims_limp)) - 0.075)), 3)

    if vecs_ruido:
        sims_r = []
        for i, v in enumerate(vecs_ruido):
            otros = vecs_limpios + [vecs_ruido[j] for j in range(len(vecs_ruido)) if j != i]
            c_o = _centroide(otros)
            s = _puntuar_vector(v, f0_mediana, [c_o, c_limpio], otros, mu_16, sigma_16, f0_mediana, f0_tol, True)
            sims_r.append(s)
        umbral_ruido = round(max(0.62, min(0.75, float(min(sims_r)) - 0.065)), 3)
    else:
        umbral_ruido = round(max(0.64, umbral_limpio - 0.10), 3)

    datos = {
        "version": VERSION_PERFIL,
        "propietario": "Luis Maximiliano Guzmán Ortiz (Max)",
        "fecha_registro": time.strftime("%Y-%m-%d %H:%M:%S"),
        "centroide_global": c_global.tolist(),
        "centroide_limpio": c_limpio.tolist(),
        "centroide_ruido": c_ruido.tolist() if c_ruido is not None else [],
        "vectores": [v.tolist() for v in todos_vecs],
        "mu_16": mu_16.tolist(),
        "sigma_16": sigma_16.tolist(),
        "f0_mediana": f0_mediana,
        "f0_tolerancia": f0_tol,
        "umbral": umbral_limpio,
        "umbral_ruido": umbral_ruido,
        "consistencia_limpia": [round(x, 3) for x in sims_limp],
    }
    ARCHIVO_PERFIL_VOZ.write_text(json.dumps(datos, indent=2), encoding="utf-8")

    print("============================================================")
    print(f"[OK] Perfil Vocal Dual v4 guardado en {ARCHIVO_PERFIL_VOZ}")
    print(f"     Muestras totales: {len(todos_vecs)} ({len(vecs_limpios)} silencio + {len(vecs_ruido)} música)")
    print(f"     Tono base (F0): {f0_mediana} Hz (±{f0_tol} Hz)")
    print(f"     Umbral silencio: {umbral_limpio} | Umbral con música/ruido: {umbral_ruido}")
    print("============================================================\n")


def ajustar_umbral_manual(nuevo_umbral: float) -> None:
    if not ARCHIVO_PERFIL_VOZ.exists():
        print("[!] Primero registra tu voz con --enroll")
        return
    datos = json.loads(ARCHIVO_PERFIL_VOZ.read_text(encoding="utf-8"))
    datos["umbral"] = round(max(0.60, min(0.92, nuevo_umbral)), 3)
    datos["umbral_ruido"] = round(max(0.55, datos["umbral"] - 0.10), 3)
    ARCHIVO_PERFIL_VOZ.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print(f"[OK] Umbrales actualizados -> Silencio: {datos['umbral']} | Música/Ruido: {datos['umbral_ruido']}")


if __name__ == "__main__":
    if "--enroll" in sys.argv:
        entrenar_perfil_vocal_max()
    elif "--umbral" in sys.argv:
        idx = sys.argv.index("--umbral")
        if idx + 1 < len(sys.argv):
            ajustar_umbral_manual(float(sys.argv[idx + 1]))
    elif "--test" in sys.argv:
        mus = _spotify_jugando_ahora()
        print(f"Habla cualquier comando durante 3.5 segundos (Spotify sonando: {'SÍ' if mus else 'NO'})...")
        wav = _grabar_muestra_wav(3.5)
        es_max, score, det = verificar_hablante(wav, musica_activa=mus)
        veredicto = "AUTORIZADO (ES MAX)" if es_max else "INVITADO NO AUTORIZADO"
        print(f"\n>>> VEREDICTO: {veredicto}\n>>> {det}\n")
    else:
        print("Uso: python jarvis_voice_id.py [--enroll | --test | --umbral 0.76]")
