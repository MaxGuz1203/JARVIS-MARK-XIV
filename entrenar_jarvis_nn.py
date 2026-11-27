#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Estudio de Dataset, Entrenamiento y Prueba en Vivo para PyTorch AudioCNN
Uso:
  python entrenar_jarvis_nn.py --grabar      # Graba tus 4 clases de audio real (~2 min)
  python entrenar_jarvis_nn.py --entrenar    # Entrena la CNN en tu GPU/CPU con Data Augmentation
  python entrenar_jarvis_nn.py --probar      # Monitor neuronal Softmax en tiempo real
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import collections
import random
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

DIRECTORIO_BASE = Path.home() / "jarvis"
if str(DIRECTORIO_BASE) not in sys.path:
    sys.path.insert(0, str(DIRECTORIO_BASE))

from jarvis_neural_core import (
    CLASES_AUDIO,
    DIR_MODELOS_NN,
    JarvisAudioCNN,
    MUESTRAS_VENTANA,
    RUTA_MODELO_AUDIO,
    SAMPLE_RATE_NN,
    predecir_ventana_audio,
)

DIR_DATASET = DIRECTORIO_BASE / "dataset_nn"


def _guardar_clip(clase: str, arr: np.ndarray) -> Path:
    carpeta = DIR_DATASET / clase
    carpeta.mkdir(parents=True, exist_ok=True)
    existentes = sorted(carpeta.glob("clip_*.npy"))
    sig_num = len(existentes) + 1
    ruta = carpeta / f"clip_{sig_num:03d}_{int(time.time()*1000)%100000}.npy"
    np.save(ruta, arr.astype(np.float32))
    return ruta


def _grabar_ruido_continuo(clase: str, cantidad: int = 16) -> None:
    print(f"\n[CLASE: {clase}] Grabando {cantidad} clips automáticos de 1.0 s.")
    print("Quédate en silencio o deja ruido normal (ventiladores, calle o música bajita)...")
    input("Presiona ENTER para empezar...")
    for i in range(1, cantidad + 1):
        audio = sd.rec(MUESTRAS_VENTANA, samplerate=SAMPLE_RATE_NN, channels=1, dtype="float32")
        sd.wait()
        arr = audio.reshape(-1)
        _guardar_clip(clase, arr)
        print(f"  [{i:02d}/{cantidad}] ruido capturado (pico={np.max(np.abs(arr)):.3f})")
        time.sleep(0.12)


def _grabar_por_disparo(clase: str, instrucciones: str, cantidad: int = 16, mult_umbral: float = 3.2, piso_min: float = 0.045) -> None:
    print(f"\n[CLASE: {clase}] {instrucciones}")
    input("Presiona ENTER para calibrar 1 segundo de silencio y comenzar...")

    blk_dur = 0.04
    blk_size = int(SAMPLE_RATE_NN * blk_dur)  # 640 muestras
    pre_bloques = 7    # 0.28 s antes del pico
    post_bloques = 18  # 0.72 s después del pico (total = 25 bloques = 1.00 s)

    with sd.InputStream(samplerate=SAMPLE_RATE_NN, channels=1, dtype="float32", blocksize=blk_size) as stream:
        picos_cal = []
        for _ in range(25):
            d, _ = stream.read(blk_size)
            picos_cal.append(float(np.max(np.abs(d))))
        ruido = float(np.median(picos_cal))
        umbral = max(piso_min, ruido * mult_umbral)
        print(f"  [Calibrado] ruido={ruido:.3f} -> umbral de disparo={umbral:.3f}. ¡Empieza cuando quieras!")

        ring_pre = collections.deque(maxlen=pre_bloques)
        capturados = 0
        while capturados < cantidad:
            d, _ = stream.read(blk_size)
            x = d.reshape(-1).astype(np.float32)
            pico = float(np.max(np.abs(x)))
            ring_pre.append(x)

            if pico >= umbral and len(ring_pre) == pre_bloques:
                bloques = list(ring_pre)
                for _ in range(post_bloques):
                    dp, _ = stream.read(blk_size)
                    bloques.append(dp.reshape(-1).astype(np.float32))
                clip = np.concatenate(bloques)[:MUESTRAS_VENTANA]
                _guardar_clip(clase, clip)
                capturados += 1
                print(f"  [OK {capturados:02d}/{cantidad}] guardado (pico={np.max(np.abs(clip)):.3f})")
                # Pequeña pausa refractaria para evitar doble captura del mismo evento
                for _ in range(8):
                    stream.read(blk_size)
                ring_pre.clear()


def modo_grabar_dataset() -> None:
    print("\n============================================================")
    print("  RECOLECCIÓN DE DATASET PROPIO — J.A.R.V.I.S. PYTORCH")
    print("============================================================")
    print("Grabarás 16 ejemplos por cada una de las 4 clases (~2 minutos en total).")
    print("Tip: Varía ligeramente tu distancia y fuerza para que la red generalice mejor.\n")

    _grabar_ruido_continuo("ruido_ambiente", cantidad=16)
    _grabar_por_disparo(
        "palmada",
        "Aplaude 16 veces (una palmada clara cada ~1 segundo, variando distancia suave/normal/fuerte).",
        cantidad=16,
        mult_umbral=3.2,
        piso_min=0.06,
    )
    _grabar_por_disparo(
        "voz_max_jarvis",
        "Di 16 veces 'Jarvis' o comandos cortos ('Oye Jarvis', 'Jarvis pausa', 'Jarvis dime') con tu voz natural.",
        cantidad=16,
        mult_umbral=2.6,
        piso_min=0.035,
    )
    _grabar_por_disparo(
        "falso_golpe_o_voz",
        "Haz 16 sonidos FALSOS: golpes en el escritorio, teclear fuerte, chasquidos y palabras que NO sean Jarvis (o voces de un video).",
        cantidad=16,
        mult_umbral=2.8,
        piso_min=0.045,
    )
    print("\n[OK] Dataset guardado en ~/jarvis/dataset_nn/. Siguiente paso: ejecutar --entrenar\n")


class DatasetAudioJarvis(Dataset):
    def __init__(self, muestras: list[tuple[np.ndarray, int]], ruidos_fondo: list[np.ndarray], entrenar: bool = True, factor_aug: int = 10):
        self.muestras = muestras
        self.ruidos_fondo = ruidos_fondo
        self.entrenar = entrenar
        self.factor_aug = factor_aug if entrenar else 1

    def __len__(self) -> int:
        return len(self.muestras) * self.factor_aug

    def __getitem__(self, idx: int):
        wav, label = self.muestras[idx % len(self.muestras)]
        x = wav.copy()

        if self.entrenar:
            # 1. Desplazamiento temporal aleatorio (±0.18 s)
            shift = random.randint(-2880, 2880)
            x = np.roll(x, shift)
            # 2. Variación aleatoria de volumen / distancia al micrófono
            ganancia = random.uniform(0.55, 1.45)
            x = x * ganancia
            # 3. Mezcla ligera con ruido ambiental real de tu cuarto (para robustez)
            if label != 0 and self.ruidos_fondo and random.random() < 0.60:
                ruido = random.choice(self.ruidos_fondo)
                alpha = random.uniform(0.06, 0.32)
                x = x + alpha * ruido
            # 4. Ruido gaussiano térmico sutil
            if random.random() < 0.50:
                x = x + np.random.normal(0.0, random.uniform(0.0008, 0.008), size=x.shape).astype(np.float32)
            x = np.clip(x, -1.0, 1.0)

        return torch.from_numpy(x.astype(np.float32)), torch.tensor(label, dtype=torch.long)


def modo_entrenar_modelo(epocas: int = 35) -> None:
    print("\n============================================================")
    print("  ENTRENAMIENTO DE RED NEURONAL PYTORCH (JarvisAudioCNN)")
    print("============================================================")

    por_clase = {}
    for idx_c, nombre_c in enumerate(CLASES_AUDIO):
        carpeta = DIR_DATASET / nombre_c
        archivos = sorted(carpeta.glob("*.npy")) if carpeta.exists() else []
        clips = []
        for f in archivos:
            arr = np.load(f).astype(np.float32).reshape(-1)
            if len(arr) < MUESTRAS_VENTANA:
                arr = np.pad(arr, (0, MUESTRAS_VENTANA - len(arr)))
            else:
                arr = arr[:MUESTRAS_VENTANA]
            clips.append(arr)
        por_clase[idx_c] = clips
        print(f"  Clase [{idx_c}] {nombre_c:<20}: {len(clips)} grabaciones")

    if any(len(v) < 6 for v in por_clase.values()):
        print("\n[!] Necesitas al menos 6 grabaciones por clase. Ejecuta primero: --grabar")
        return

    rng = random.Random(42)
    train_items, val_items = [], []
    for idx_c, clips in por_clase.items():
        copia = list(clips)
        rng.shuffle(copia)
        n_val = max(2, int(round(len(copia) * 0.22)))
        for c in copia[:n_val]:
            val_items.append((c, idx_c))
        for c in copia[n_val:]:
            train_items.append((c, idx_c))

    ruidos_train = [c for c, y in train_items if y == 0]
    ds_train = DatasetAudioJarvis(train_items, ruidos_train, entrenar=True, factor_aug=10)
    ds_val = DatasetAudioJarvis(val_items, [], entrenar=False, factor_aug=1)

    batch_size = min(16, len(ds_train))
    dl_train = DataLoader(ds_train, batch_size=batch_size, shuffle=True, drop_last=(len(ds_train) % batch_size == 1))
    dl_val = DataLoader(ds_val, batch_size=16, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDispositivo de entrenamiento: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"Muestras -> Train: {len(train_items)} reales ({len(ds_train)} aumentadas/época) | Val: {len(val_items)} reales\n")

    modelo = JarvisAudioCNN(num_clases=len(CLASES_AUDIO)).to(device)
    criterio = nn.CrossEntropyLoss(label_smoothing=0.05)
    optimizador = torch.optim.AdamW(modelo.parameters(), lr=2.2e-3, weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizador, T_max=epocas)

    mejor_val_acc = -1.0
    mejor_val_loss = 999.0
    mejor_estado = None
    t_inicio = time.time()

    for ep in range(1, epocas + 1):
        modelo.train()
        loss_tr, ok_tr, tot_tr = 0.0, 0, 0
        for bx, by in dl_train:
            bx, by = bx.to(device), by.to(device)
            optimizador.zero_grad(set_to_none=True)
            out = modelo(bx, aplicar_spec_augment=True)
            loss = criterio(out, by)
            loss.backward()
            optimizador.step()

            loss_tr += loss.item() * len(by)
            ok_tr += int((out.argmax(dim=1) == by).sum().item())
            tot_tr += len(by)
        scheduler.step()

        modelo.eval()
        loss_v, ok_v, tot_v = 0.0, 0, 0
        with torch.no_grad():
            for bx, by in dl_val:
                bx, by = bx.to(device), by.to(device)
                out = modelo(bx, aplicar_spec_augment=False)
                loss = criterio(out, by)
                loss_v += loss.item() * len(by)
                ok_v += int((out.argmax(dim=1) == by).sum().item())
                tot_v += len(by)

        tr_acc = ok_tr / max(1, tot_tr)
        val_acc = ok_v / max(1, tot_v)
        val_loss = loss_v / max(1, tot_v)

        if val_acc > mejor_val_acc or (val_acc == mejor_val_acc and val_loss < mejor_val_loss):
            mejor_val_acc = val_acc
            mejor_val_loss = val_loss
            mejor_estado = {k: v.detach().cpu().clone() for k, v in modelo.state_dict().items()}

        if ep == 1 or ep % 5 == 0 or ep == epocas:
            print(f"  Época {ep:02d}/{epocas} | Train Loss: {loss_tr/tot_tr:.4f} Acc: {tr_acc*100:5.1f}% | Val Loss: {val_loss:.4f} Acc: {val_acc*100:5.1f}%")

    # Evaluar matriz de confusión del mejor modelo
    modelo.load_state_dict(mejor_estado)
    modelo.eval()
    matriz = np.zeros((len(CLASES_AUDIO), len(CLASES_AUDIO)), dtype=int)
    with torch.no_grad():
        for bx, by in dl_val:
            preds = modelo(bx.to(device)).argmax(dim=1).cpu().numpy()
            for real, pred in zip(by.numpy(), preds):
                matriz[real, pred] += 1

    DIR_MODELOS_NN.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": mejor_estado,
            "clases": list(CLASES_AUDIO),
            "val_acc": float(mejor_val_acc),
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "arquitectura": "JarvisAudioCNN_v1_LogMelDual",
        },
        RUTA_MODELO_AUDIO,
    )

    print("\n--- Matriz de Confusión (Filas=Real, Columnas=Predicción) ---")
    encabezado = "                    " + " ".join(f"{c[:8]:>9}" for c in CLASES_AUDIO)
    print(encabezado)
    for i, c in enumerate(CLASES_AUDIO):
        fila = " ".join(f"{matriz[i, j]:9d}" for j in range(len(CLASES_AUDIO)))
        print(f"  {c:<18}{fila}")

    print(f"\n[OK] Modelo guardado en {RUTA_MODELO_AUDIO}")
    print(f"     Mejor Accuracy en Validación: {mejor_val_acc*100:.1f}% | Tiempo total: {time.time() - t_inicio:.1f}s\n")


def modo_probar_en_vivo() -> None:
    if not RUTA_MODELO_AUDIO.exists():
        print("[!] Aún no existe el modelo entrenado. Ejecuta --grabar y luego --entrenar.")
        return
    print("\n============================================================")
    print("  MONITOR NEURONAL PYTORCH EN TIEMPO REAL (Ctrl+C salir)")
    print("============================================================")
    print("Prueba aplaudir, decir 'Jarvis', golpear la mesa o quedarte en silencio:\n")

    blk_size = int(SAMPLE_RATE_NN * 0.20)  # actualiza 5 veces por segundo
    ring = np.zeros(MUESTRAS_VENTANA, dtype=np.float32)

    with sd.InputStream(samplerate=SAMPLE_RATE_NN, channels=1, dtype="float32", blocksize=blk_size) as stream:
        while True:
            d, _ = stream.read(blk_size)
            nuevo = d.reshape(-1).astype(np.float32)
            ring = np.concatenate([ring[len(nuevo):], nuevo])
            res = predecir_ventana_audio(ring)
            if res:
                p = res["probs"]
                print(
                    f"\r[{res['dispositivo'].upper()} {res['latencia_ms']:4.1f}ms] "
                    f"Ruido:{p['ruido_ambiente']*100:4.1f}% | "
                    f"Palmada:{p['palmada']*100:4.1f}% | "
                    f"VozMax:{p['voz_max_jarvis']*100:4.1f}% | "
                    f"Falso:{p['falso_golpe_o_voz']*100:4.1f}%  ==> {res['clase'].upper():<18}",
                    end="",
                    flush=True,
                )


if __name__ == "__main__":
    if "--grabar" in sys.argv:
        modo_grabar_dataset()
    elif "--entrenar" in sys.argv:
        modo_entrenar_modelo()
    elif "--probar" in sys.argv:
        try:
            modo_probar_en_vivo()
        except KeyboardInterrupt:
            print("\n[OK] Monitor neuronal cerrado.")
    else:
        print("Uso: python entrenar_jarvis_nn.py [--grabar | --entrenar | --probar]")
