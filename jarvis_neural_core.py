#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Núcleo Neuronal Real en PyTorch (Módulo 1: JarvisAudioCNN)
- Red Neuronal Convolucional 2D sobre Espectrogramas Log-Mel de doble canal (forma + energía).
- Soporta inferencia en ventana única (palmadas) y análisis por lotes de clips WAV (escucha continua).
- Calentamiento CUDA automático para eliminar el retraso de la primera inferencia.
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import io
import time
import wave
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

DIRECTORIO_BASE = Path.home() / "jarvis"
DIR_MODELOS_NN = DIRECTORIO_BASE / "modelos_nn"
RUTA_MODELO_AUDIO = DIR_MODELOS_NN / "jarvis_audio_cnn.pt"

SAMPLE_RATE_NN = 16000
MUESTRAS_VENTANA = 16000  # 1.0 segundo exacto

CLASES_AUDIO = [
    "ruido_ambiente",     # 0: Silencio, ventiladores, cuarto normal o música de fondo
    "palmada",            # 1: Palmada real de Max
    "voz_max_jarvis",     # 2: Voz de Max diciendo "Jarvis" o activando comandos
    "falso_golpe_o_voz",  # 3: Golpes en la mesa, teclas, chasquidos u otras voces
]


def _construir_banco_mel_np(
    sr: int = SAMPLE_RATE_NN,
    n_fft: int = 512,
    n_mels: int = 64,
    f_min: float = 80.0,
    f_max: float = 7600.0,
) -> np.ndarray:
    def hz_to_mel(hz):
        return 2595.0 * np.log10(1.0 + hz / 700.0)

    def mel_to_hz(mel):
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    mels = np.linspace(hz_to_mel(f_min), hz_to_mel(f_max), n_mels + 2)
    hz = mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    n_bins = n_fft // 2 + 1
    fb = np.zeros((n_mels, n_bins), dtype=np.float32)

    for m in range(1, n_mels + 1):
        b_izq, b_cen, b_der = bins[m - 1], bins[m], bins[m + 1]
        if b_cen > b_izq:
            for k in range(b_izq, min(b_cen, n_bins)):
                fb[m - 1, k] = (k - b_izq) / float(b_cen - b_izq)
        if b_der > b_cen:
            for k in range(b_cen, min(b_der, n_bins)):
                fb[m - 1, k] = (b_der - k) / float(b_der - b_cen)
    return fb


class LogMelDualExtractor(nn.Module):
    """Convierte audio 1D (B, 16000) en un tensor 2D de 2 canales (B, 2, 64, 101)."""

    def __init__(self, sr: int = SAMPLE_RATE_NN, n_fft: int = 512, hop_length: int = 160, win_length: int = 400, n_mels: int = 64):
        super().__init__()
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.win_length = win_length
        self.register_buffer("hann_win", torch.hann_window(win_length, dtype=torch.float32))
        self.register_buffer("mel_fb", torch.from_numpy(_construir_banco_mel_np(sr, n_fft, n_mels)))

    def forward(self, wav: torch.Tensor) -> torch.Tensor:
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        stft = torch.stft(
            wav,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            win_length=self.win_length,
            window=self.hann_win,
            center=True,
            return_complex=True,
        )
        power = stft.real.pow(2) + stft.imag.pow(2)
        mel = torch.matmul(self.mel_fb, power).clamp(min=1e-7)
        log_mel = torch.log(mel)

        media = log_mel.mean(dim=(1, 2), keepdim=True)
        std = log_mel.std(dim=(1, 2), keepdim=True).clamp(min=1e-5)
        ch_forma = (log_mel - media) / std
        ch_energia = (log_mel + 10.0) / 10.0
        return torch.stack([ch_forma, ch_energia], dim=1)


class JarvisAudioCNN(nn.Module):
    """Red Neuronal Convolucional 2D (~77.5k parámetros) para eventos acústicos de J.A.R.V.I.S."""

    def __init__(self, num_clases: int = len(CLASES_AUDIO)):
        super().__init__()
        self.extractor = LogMelDualExtractor()
        self.bloques_conv = nn.Sequential(
            nn.Conv2d(2, 24, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(24),
            nn.GELU(),
            nn.MaxPool2d(kernel_size=2),

            nn.Conv2d(24, 48, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(48),
            nn.GELU(),
            nn.MaxPool2d(kernel_size=2),

            nn.Conv2d(48, 96, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(96),
            nn.GELU(),
            nn.AdaptiveAvgPool2d((2, 2)),
        )
        self.cabeza = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.30),
            nn.Linear(96 * 4, 64),
            nn.GELU(),
            nn.Dropout(0.20),
            nn.Linear(64, num_clases),
        )

    def _spec_augment(self, x: torch.Tensor) -> torch.Tensor:
        b, _, f_dim, t_dim = x.shape
        x = x.clone()
        for i in range(b):
            if torch.rand(1).item() < 0.65:
                fw = int(torch.randint(4, 10, (1,)).item())
                f0 = int(torch.randint(0, max(1, f_dim - fw), (1,)).item())
                x[i, :, f0 : f0 + fw, :] = 0.0
            if torch.rand(1).item() < 0.65:
                tw = int(torch.randint(6, 16, (1,)).item())
                t0 = int(torch.randint(0, max(1, t_dim - tw), (1,)).item())
                x[i, :, :, t0 : t0 + tw] = 0.0
        return x

    def forward(self, wav: torch.Tensor, aplicar_spec_augment: bool = False) -> torch.Tensor:
        spec = self.extractor(wav)
        if self.training and aplicar_spec_augment:
            spec = self._spec_augment(spec)
        feat = self.bloques_conv(spec)
        return self.cabeza(feat)


class _MotorInferenciaAudio:
    def __init__(self):
        self.modelo = None
        self.clases = list(CLASES_AUDIO)
        self.dispositivo = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mtime_cargado = 0.0
        self.val_acc = 0.0
        self._calentado = False

    def _cargar_si_necesario(self) -> bool:
        if not RUTA_MODELO_AUDIO.exists():
            return False
        mtime = RUTA_MODELO_AUDIO.stat().st_mtime
        if self.modelo is not None and mtime == self.mtime_cargado:
            return True
        try:
            ckpt = torch.load(RUTA_MODELO_AUDIO, map_location=self.dispositivo, weights_only=True)
            clases = list(ckpt.get("clases", CLASES_AUDIO))
            modelo = JarvisAudioCNN(num_clases=len(clases)).to(self.dispositivo)
            modelo.load_state_dict(ckpt["state_dict"])
            modelo.eval()
            self.modelo = modelo
            self.clases = clases
            self.mtime_cargado = mtime
            self.val_acc = float(ckpt.get("val_acc", 0.0))
            self._calentado = False
            return True
        except Exception:
            self.modelo = None
            return False

    def calentar(self) -> None:
        if self._cargar_si_necesario() and not self._calentado:
            with torch.no_grad():
                dummy = torch.zeros((1, MUESTRAS_VENTANA), dtype=torch.float32, device=self.dispositivo)
                _ = self.modelo(dummy, aplicar_spec_augment=False)
            self._calentado = True

    def predecir(self, audio_float32: np.ndarray) -> dict | None:
        if not self._cargar_si_necesario():
            return None
        t0 = time.perf_counter()
        arr = np.asarray(audio_float32, dtype=np.float32).reshape(-1)
        if len(arr) < MUESTRAS_VENTANA:
            arr = np.concatenate([np.zeros(MUESTRAS_VENTANA - len(arr), dtype=np.float32), arr])
        elif len(arr) > MUESTRAS_VENTANA:
            arr = arr[-MUESTRAS_VENTANA:]

        tensor = torch.from_numpy(arr).unsqueeze(0).to(self.dispositivo)
        with torch.no_grad():
            logits = self.modelo(tensor, aplicar_spec_augment=False)
            probs_t = torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()

        idx = int(np.argmax(probs_t))
        lat_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "clase": self.clases[idx],
            "confianza": float(probs_t[idx]),
            "probs": {c: float(probs_t[i]) for i, c in enumerate(self.clases)},
            "dispositivo": str(self.dispositivo),
            "latencia_ms": round(lat_ms, 2),
        }

    def analizar_clip_wav(self, wav_bytes: bytes) -> dict | None:
        """
        Evalúa un clip WAV completo en 1 solo batch de GPU con ventanas solapadas de 1.0 s (paso 0.5 s).
        Permite descartar ruido/palmadas/golpes secos en <2 ms antes de llamar a Google STT y detectar voz_max_jarvis.
        """
        if not self._cargar_si_necesario():
            return None
        t0 = time.perf_counter()
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sr = wf.getframerate()
                n_ch = wf.getnchannels()
                raw = wf.readframes(wf.getnframes())
        except Exception:
            return None

        sig = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if n_ch > 1:
            sig = sig.reshape(-1, n_ch).mean(axis=1)
        if len(sig) < 1600:
            return None

        if sr != SAMPLE_RATE_NN:
            n_nuevo = int(round(len(sig) * SAMPLE_RATE_NN / float(sr)))
            sig = np.interp(np.linspace(0, len(sig) - 1, n_nuevo), np.arange(len(sig)), sig).astype(np.float32)

        duracion_s = len(sig) / float(SAMPLE_RATE_NN)
        ventanas = []
        if len(sig) <= MUESTRAS_VENTANA:
            pad = np.zeros(MUESTRAS_VENTANA - len(sig), dtype=np.float32)
            ventanas.append(np.concatenate([pad, sig]))
        else:
            hop = MUESTRAS_VENTANA // 2  # 0.5 s
            for ini in range(0, len(sig) - MUESTRAS_VENTANA + 1, hop):
                ventanas.append(sig[ini : ini + MUESTRAS_VENTANA])
                if len(ventanas) >= 12:
                    break
            if (len(sig) - MUESTRAS_VENTANA) % hop != 0 and len(ventanas) < 13:
                ventanas.append(sig[-MUESTRAS_VENTANA:])

        batch_np = np.stack(ventanas, axis=0)
        batch_t = torch.from_numpy(batch_np).to(self.dispositivo)
        with torch.no_grad():
            logits = self.modelo(batch_t, aplicar_spec_augment=False)
            probs = torch.softmax(logits, dim=-1).detach().cpu().numpy()

        mapa = {c: i for i, c in enumerate(self.clases)}
        i_ruido = mapa.get("ruido_ambiente", 0)
        i_clap = mapa.get("palmada", 1)
        i_voz = mapa.get("voz_max_jarvis", 2)
        i_falso = mapa.get("falso_golpe_o_voz", 3)

        mean_ruido = float(np.mean(probs[:, i_ruido]))
        max_clap = float(np.max(probs[:, i_clap]))
        max_voz = float(np.max(probs[:, i_voz]))
        max_falso = float(np.max(probs[:, i_falso]))

        # Calcular duración ACTIVA real (sin contar los ~0.95 s de pre-roll y silencio final del VAD)
        blk_20 = 320
        n_b = len(sig) // blk_20
        if n_b > 0:
            rms_b = np.sqrt(np.mean(sig[: n_b * blk_20].reshape(n_b, blk_20) ** 2, axis=1))
            umb_act = max(0.014, float(np.percentile(rms_b, 95)) * 0.22)
            duracion_activa_s = float(np.sum(rms_b >= umb_act)) * 0.02
        else:
            duracion_activa_s = duracion_s

        # Compuerta local: descarta ruido, palmadas sueltas o golpes secos cortos (act<=0.48 s),
        # pero deja pasar frases completas de amigos (act>0.48 s) para conservar el Modo Invitado.
        descartar = False
        motivo = "voz_o_habla_detectada"
        if mean_ruido >= 0.65 and max_voz < 0.18 and max_falso < 0.30:
            descartar = True
            motivo = f"ruido_ambiente({mean_ruido*100:.0f}%)"
        elif max_clap >= 0.70 and max_voz < 0.28 and duracion_activa_s <= 0.50:
            descartar = True
            motivo = f"palmada_suelta({max_clap*100:.0f}%, act={duracion_activa_s:.2f}s)"
        elif max_falso >= 0.74 and max_voz < 0.55 and duracion_activa_s <= 0.48:
            descartar = True
            motivo = f"golpe_breve({max_falso*100:.0f}%, act={duracion_activa_s:.2f}s)"

        lat_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "descartar_local": descartar,
            "motivo_descarte": motivo,
            "detecto_voz_max": max_voz >= 0.68,
            "confianza_voz_max": max_voz,
            "max_palmada": max_clap,
            "mean_ruido": mean_ruido,
            "max_falso": max_falso,
            "ventanas": len(ventanas),
            "duracion_s": round(duracion_s, 2),
            "dispositivo": str(self.dispositivo),
            "latencia_ms": round(lat_ms, 2),
        }


_MOTOR_AUDIO = _MotorInferenciaAudio()


def calentar_gpu_audio() -> None:
    _MOTOR_AUDIO.calentar()


def predecir_ventana_audio(audio_float32: np.ndarray) -> dict | None:
    return _MOTOR_AUDIO.predecir(audio_float32)


def analizar_clip_wav_con_cnn(wav_bytes: bytes) -> dict | None:
    return _MOTOR_AUDIO.analizar_clip_wav(wav_bytes)


def info_nucleo_neuronal() -> str:
    dev = "GPU CUDA (" + torch.cuda.get_device_name(0) + ")" if torch.cuda.is_available() else "CPU"
    if _MOTOR_AUDIO._cargar_si_necesario():
        n_params = sum(p.numel() for p in _MOTOR_AUDIO.modelo.parameters())
        return f"PyTorch AudioCNN ACTIVA en {dev} ({n_params:,} parámetros | ValAcc: {_MOTOR_AUDIO.val_acc*100:.1f}%)"
    return f"PyTorch listo en {dev} (sin pesos entrenados aún; ejecuta entrenar_jarvis_nn.py)"
