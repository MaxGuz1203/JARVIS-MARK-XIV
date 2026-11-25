#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Motor de Biometría y Verificación Vocal (MFCC + Deltas + Tono F0)
- Distingue el timbre y tono de voz de Max frente a cualquier otra persona en <15 ms.
- 100% local en NumPy (sin dependencias pesadas ni internet).
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import io
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

DIRECTORIO_BASE = Path.home() / "jarvis"
ARCHIVO_PERFIL_VOZ = DIRECTORIO_BASE / "voz_max.json"
SAMPLE_RATE_DEFAULT = 16000


def _hz_a_mel(hz: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(hz, dtype=np.float64) / 700.0)


def _mel_a_hz(mel: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (10.0 ** (np.asarray(mel, dtype=np.float64) / 2595.0) - 1.0)


def _banco_filtros_mel(sr: int, n_fft: int = 512, n_mels: int = 26) -> np.ndarray:
    f_min = 80.0
    f_max = min(7600.0, sr / 2.0)
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


def _matriz_dct(n_mfcc: int = 20, n_mels: int = 26) -> np.ndarray:
    k = np.arange(n_mfcc)[:, None]
    n = np.arange(n_mels)[None, :]
    return np.cos(np.pi * k * (n + 0.5) / float(n_mels)) * np.sqrt(2.0 / float(n_mels))


def _estimar_tono_f0(frames_crudos: np.ndarray, sr: int) -> tuple[float, float]:
    """Estima la frecuencia fundamental (pitch F0 en Hz) mediante autocorrelación."""
    min_lag = max(1, int(sr / 380.0))
    max_lag = min(frames_crudos.shape[1] - 1, int(sr / 70.0))
    if max_lag <= min_lag:
        return 0.0, 0.0

    f0s = []
    for fr in frames_crudos:
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
        if ventana[idx] > 0.36:
            lag = min_lag + idx
            f0s.append(sr / float(lag))

    if len(f0s) < 3:
        return 0.0, 0.0
    arr = np.asarray(f0s, dtype=np.float64)
    med = float(np.median(arr))
    iqr = float(np.percentile(arr, 75) - np.percentile(arr, 25))
    return med, iqr


def extraer_firma_vocal(wav_bytes: bytes) -> dict | None:
    """Extrae el vector biométrico de timbre (57 dimensiones) y el tono F0 desde bytes WAV."""
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

    frame_len = int(sr * 0.025)
    hop_len = int(sr * 0.010)
    if len(sig) < frame_len * 6:
        return None

    # Enmarcado crudo (para detección de voz activa y tono F0)
    n_frames = 1 + (len(sig) - frame_len) // hop_len
    frames_crudos = np.array([sig[i * hop_len : i * hop_len + frame_len] for i in range(n_frames)])
    rms = np.sqrt(np.mean(frames_crudos ** 2, axis=1))
    umbral_activo = max(0.012, float(np.percentile(rms, 75)) * 0.35)
    mascara = rms >= umbral_activo

    if int(np.sum(mascara)) < 8:
        top_idx = np.argsort(rms)[-max(6, n_frames // 4):]
        mascara = np.zeros(n_frames, dtype=bool)
        mascara[top_idx] = True

    activos_crudos = frames_crudos[mascara]

    # Pre-énfasis para resaltar formantes del tracto vocal
    sig_emph = np.append(sig[0], sig[1:] - 0.97 * sig[:-1])
    frames_emph = np.array([sig_emph[i * hop_len : i * hop_len + frame_len] for i in range(n_frames)])[mascara]

    n_fft = 512
    ventana = np.hamming(frame_len)[None, :]
    espectro = np.abs(np.fft.rfft(frames_emph * ventana, n=n_fft))
    potencia = (espectro ** 2) / float(n_fft)

    fb = _banco_filtros_mel(sr, n_fft=n_fft, n_mels=26)
    log_mel = np.log(np.maximum(np.dot(potencia, fb.T), 1e-10))
    dct = _matriz_dct(n_mfcc=20, n_mels=26)
    mfccs = np.dot(log_mel, dct.T)

    # Descartamos C0 (volumen) y conservamos C1..C19 (timbre puro)
    c = mfccs[:, 1:]
    deltas = np.diff(c, axis=0) if len(c) > 1 else np.zeros_like(c)

    media_c = np.mean(c, axis=0)
    std_c = np.std(c, axis=0)
    std_d = np.std(deltas, axis=0)

    vec = np.concatenate([media_c, 0.45 * std_c, 0.30 * std_d])
    norma = float(np.linalg.norm(vec))
    if norma < 1e-8 or not np.all(np.isfinite(vec)):
        return None
    vec = vec / norma

    f0_med, f0_iqr = _estimar_tono_f0(activos_crudos, sr)
    return {
        "vector": vec.tolist(),
        "f0": round(f0_med, 2),
        "f0_iqr": round(f0_iqr, 2),
        "frames_activos": int(len(activos_crudos)),
    }


def perfil_vocal_existe() -> bool:
    return ARCHIVO_PERFIL_VOZ.exists()


def verificar_hablante(wav_bytes: bytes) -> tuple[bool, float, str]:
    """
    Devuelve (es_max, puntuacion_0_a_1, diagnostico).
    Si aún no se ha registrado la voz de Max, permite paso seguro para no bloquear el asistente.
    """
    if not ARCHIVO_PERFIL_VOZ.exists():
        return True, 1.0, "Sin perfil vocal registrado (ejecute --enroll)"

    firma = extraer_firma_vocal(wav_bytes)
    if not firma:
        return False, 0.0, "Audio insuficiente para verificación biométrica"

    try:
        perfil = json.loads(ARCHIVO_PERFIL_VOZ.read_text(encoding="utf-8"))
        centroide = np.asarray(perfil["centroide"], dtype=np.float64)
        vectores = [np.asarray(v, dtype=np.float64) for v in perfil["vectores"]]
        f0_ref = float(perfil.get("f0_mediana", 0.0))
        f0_tol = float(perfil.get("f0_tolerancia", 40.0))
        umbral = float(perfil.get("umbral", 0.84))
    except Exception:
        return True, 1.0, "Error leyendo perfil vocal"

    vec = np.asarray(firma["vector"], dtype=np.float64)
    sim_centroide = float(np.dot(vec, centroide))
    sim_max = max(float(np.dot(vec, v)) for v in vectores)
    sim_timbre = 0.65 * sim_centroide + 0.35 * sim_max

    penalizacion_f0 = 0.0
    f0_actual = float(firma.get("f0", 0.0))
    if f0_actual > 0.0 and f0_ref > 0.0:
        diff_f0 = abs(f0_actual - f0_ref)
        if diff_f0 > f0_tol:
            penalizacion_f0 = min(0.28, ((diff_f0 - f0_tol) / 110.0) * 0.28)

    score_final = max(0.0, min(1.0, sim_timbre - penalizacion_f0))
    es_max = score_final >= umbral
    detalle = (
        f"Score={score_final:.3f} (Umbral={umbral:.3f} | Timbre={sim_timbre:.3f} | "
        f"Tono={f0_actual:.0f}Hz vs Ref={f0_ref:.0f}Hz)"
    )
    return es_max, score_final, detalle


def _grabar_muestra_wav(segundos: float = 4.5, sr: int = SAMPLE_RATE_DEFAULT) -> bytes:
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


def entrenar_perfil_vocal_max() -> None:
    frases = [
        "Jarvis, dime qué es lo que se muestra en mi pantalla ahora mismo.",
        "Jarvis, proyecta un modelo tres D del motor de inducción tipo jaula de ardilla.",
        "Jarvis, cambia la canción de Spotify y revisa mis pendientes de Classroom.",
        "Jarvis, abre Onshape, Canva y LaTeX en mi estación de trabajo.",
        "Jarvis, clipea los últimos quince segundos y guarda una caja negra.",
        "Jarvis, activa el modo ahorro de batería y dime el estado del sistema.",
    ]
    print("\n============================================================")
    print("  REGISTRO BIOMÉTRICO VOCAL DE MAX — J.A.R.V.I.S.")
    print("============================================================")
    print("Lee cada frase con tu voz natural a la distancia normal de tu laptop.\n")

    vectores = []
    f0s = []

    for i, frase in enumerate(frases, start=1):
        while True:
            input(f"[{i}/{len(frases)}] Presiona ENTER y lee en voz alta:\n  » \"{frase}\"\n")
            print("  🔴 Grabando (4.5 segundos)...")
            wav_b = _grabar_muestra_wav(4.5)
            firma = extraer_firma_vocal(wav_b)
            if firma and firma["frames_activos"] >= 35:
                vectores.append(np.asarray(firma["vector"], dtype=np.float64))
                if firma["f0"] > 0:
                    f0s.append(firma["f0"])
                print(f"  [OK] Muestra {i} capturada (Tono detectado: {firma['f0']:.1f} Hz | Frames: {firma['frames_activos']})\n")
                break
            print("  [!] Audio muy bajo o corto. Intenta hablar un poco más claro.\n")

    matriz = np.vstack(vectores)
    centroide = np.mean(matriz, axis=0)
    centroide = centroide / np.linalg.norm(centroide)

    # Auto-calibración del umbral mediante validación cruzada leave-one-out
    sims_loo = []
    for i in range(len(vectores)):
        otros = [vectores[j] for j in range(len(vectores)) if j != i]
        c_loo = np.mean(np.vstack(otros), axis=0)
        c_loo = c_loo / np.linalg.norm(c_loo)
        s_c = float(np.dot(vectores[i], c_loo))
        s_m = max(float(np.dot(vectores[i], v)) for v in otros)
        sims_loo.append(0.65 * s_c + 0.35 * s_m)

    min_propio = float(min(sims_loo))
    umbral_auto = round(max(0.80, min(0.90, min_propio - 0.05)), 3)
    f0_mediana = round(float(np.median(f0s)), 2) if f0s else 0.0
    f0_tol = round(max(36.0, float(np.std(f0s)) * 2.4), 2) if len(f0s) >= 2 else 42.0

    datos = {
        "propietario": "Luis Maximiliano Guzmán Ortiz (Max)",
        "fecha_registro": time.strftime("%Y-%m-%d %H:%M:%S"),
        "centroide": centroide.tolist(),
        "vectores": [v.tolist() for v in vectores],
        "f0_mediana": f0_mediana,
        "f0_tolerancia": f0_tol,
        "umbral": umbral_auto,
        "consistencia_interna": [round(x, 3) for x in sims_loo],
    }
    ARCHIVO_PERFIL_VOZ.write_text(json.dumps(datos, indent=2), encoding="utf-8")

    print("============================================================")
    print(f"[OK] Firma vocal de Max guardada en {ARCHIVO_PERFIL_VOZ}")
    print(f"     Tono medio (F0): {f0_mediana} Hz (±{f0_tol} Hz)")
    print(f"     Consistencia interna: {[round(x, 3) for x in sims_loo]}")
    print(f"     Umbral calibrado automáticamente: {umbral_auto}")
    print("============================================================\n")


def ajustar_umbral_manual(nuevo_umbral: float) -> None:
    if not ARCHIVO_PERFIL_VOZ.exists():
        print("[!] Primero registra tu voz con --enroll")
        return
    datos = json.loads(ARCHIVO_PERFIL_VOZ.read_text(encoding="utf-8"))
    datos["umbral"] = round(max(0.65, min(0.96, nuevo_umbral)), 3)
    ARCHIVO_PERFIL_VOZ.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print(f"[OK] Nuevo umbral biométrico establecido en {datos['umbral']}")


if __name__ == "__main__":
    if "--enroll" in sys.argv:
        entrenar_perfil_vocal_max()
    elif "--umbral" in sys.argv:
        idx = sys.argv.index("--umbral")
        if idx + 1 < len(sys.argv):
            ajustar_umbral_manual(float(sys.argv[idx + 1]))
    elif "--test" in sys.argv:
        print("Habla durante 4 segundos para probar la biometría vocal (puedes probar tú o un amigo)...")
        wav = _grabar_muestra_wav(4.0)
        es_max, score, det = verificar_hablante(wav)
        veredicto = "AUTORIZADO (ES MAX)" if es_max else "INVITADO NO AUTORIZADO (BLOQUEO DE COMANDOS)"
        print(f"\n>>> VEREDICTO: {veredicto}\n>>> {det}\n")
    else:
        print("Uso: python jarvis_voice_id.py [--enroll | --test | --umbral 0.84]")
