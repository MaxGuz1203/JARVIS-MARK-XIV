#!/usr/bin/env python3
"""
J.A.R.V.I.S. - Fase 2 (v2): JarvisIntentNet Regularizada con IDF y Protección OOD
- EmbeddingBag(mode="sum") ponderado por IDF y tipo de token (palabras > bigramas > char 4-grams).
- Bloque compacto con LayerNorm + Dropout alto + amortiguación OOD para frases desconocidas.
- Compatible 100% con jarvis_brain.py y jarvis_wake.py (<0.8 ms en GPU CUDA / CPU).
Autor: Luis Maximiliano Guzmán Ortiz (Max)
"""

import re
import time
import unicodedata
from pathlib import Path

import torch
import torch.nn as nn

DIRECTORIO_BASE = Path.home() / "jarvis"
DIR_MODELOS_NN = DIRECTORIO_BASE / "modelos_nn"
RUTA_MODELO_INTENT = DIR_MODELOS_NN / "jarvis_intent_net.pt"

INTENCIONES_JARVIS = [
    "conversacion_general",   # 0
    "musica_reproducir",      # 1
    "musica_control",         # 2
    "vision_pantalla",        # 3
    "modelo_3d",              # 4
    "dossier_investigacion",  # 5
    "classroom_memoria",      # 6
    "abrir_apps_ventanas",    # 7
    "grabacion_clips",        # 8
    "hardware_energia",       # 9
    "modo_silencio",          # 10
    "seguridad_red",          # 11
    "apagar_sistema",         # 12
]

STOPWORDS_ES = {
    "de", "la", "el", "en", "y", "a", "los", "las", "un", "una", "unos", "unas",
    "me", "mi", "mis", "te", "tu", "tus", "se", "su", "sus", "es", "son", "ser",
    "que", "por", "con", "para", "del", "al", "lo", "le", "les", "como", "esta",
    "este", "esto", "estos", "estas", "estoy", "estas", "muy", "mas", "pero",
    "o", "u", "ya", "si", "aqui", "ahi", "favor", "porfa", "jarvis", "yarvis",
    "oye", "hey", "disculpa", "ahorita", "ahora", "mismo", "tantito",
}


def normalizar_texto_intent(texto: str) -> str:
    t = str(texto or "").lower().strip()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extraer_tokens_ponderados(texto: str) -> tuple[list[tuple[str, float]], list[str]]:
    """
    Devuelve (lista de (token, peso_tipo), palabras_contenido).
    Las palabras completas dominan (1.0); los char 4-grams solo aportan apoyo ligero (0.18).
    """
    norm = normalizar_texto_intent(texto)
    palabras = [p for p in norm.split() if p]
    if not palabras:
        return [("<UNK>", 1.0)], []

    contenido = [p for p in palabras if p not in STOPWORDS_ES and (len(p) >= 2 or p.isdigit())]
    tokens: list[tuple[str, float]] = []

    # 1. Palabras de contenido (peso alto)
    for p in contenido:
        tokens.append((f"w:{p}", 1.0))

    # 2. Bigramas contextuales (capturan "no me", "en 3d", "de bateria", "a fondo")
    for i in range(len(palabras) - 1):
        p1, p2 = palabras[i], palabras[i + 1]
        if p1 not in STOPWORDS_ES or p2 not in STOPWORDS_ES or p1 == "no":
            tokens.append((f"b:{p1}_{p2}", 0.85))

    # 3. Char 4-grams ligeros SOLO en palabras de contenido >= 5 letras (sin invadir palabras ajenas)
    for p in contenido:
        if len(p) >= 5:
            w_pad = f"<{p}>"
            for i in range(len(w_pad) - 3):
                tokens.append((f"c4:{w_pad[i : i + 4]}", 0.18))

    if not tokens:
        for p in palabras:
            tokens.append((f"w:{p}", 0.6))

    return tokens, contenido


def codificar_con_pesos(
    texto: str,
    vocab: dict[str, int],
    idf_map: dict[str, float],
) -> tuple[list[int], list[float], float]:
    pares, contenido = extraer_tokens_ponderados(texto)
    ids: list[int] = []
    pesos: list[float] = []

    for tok, w_tipo in pares:
        idx = vocab.get(tok)
        if idx is not None:
            ids.append(idx)
            pesos.append(w_tipo * float(idf_map.get(tok, 1.0)))

    if contenido:
        conocidas = sum(1 for p in contenido if f"w:{p}" in vocab)
        ratio_conocidas = conocidas / float(len(contenido))
    else:
        ratio_conocidas = 0.0

    if not ids:
        return [1], [1.0], 0.0

    suma = sum(pesos)
    if suma <= 1e-8:
        pesos = [1.0 / len(ids)] * len(ids)
    else:
        pesos = [w / suma for w in pesos]
    return ids, pesos, ratio_conocidas


class JarvisIntentNet(nn.Module):
    """Clasificador Neuronal Compacto y Regularizado sobre EmbeddingBag ponderado por IDF."""

    def __init__(self, vocab_size: int, num_clases: int = len(INTENCIONES_JARVIS), embed_dim: int = 48, hidden_dim: int = 64):
        super().__init__()
        self.emb = nn.EmbeddingBag(vocab_size, embed_dim, mode="sum")
        self.red = nn.Sequential(
            nn.LayerNorm(embed_dim),
            nn.Dropout(0.35),
            nn.Linear(embed_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(0.35),
            nn.Linear(hidden_dim, num_clases),
        )

    def forward(self, indices: torch.Tensor, offsets: torch.Tensor, per_sample_weights: torch.Tensor) -> torch.Tensor:
        h = self.emb(indices, offsets, per_sample_weights=per_sample_weights)
        return self.red(h)


class _MotorInferenciaIntent:
    def __init__(self):
        self.modelo = None
        self.vocab = {}
        self.idf_map = {}
        self.clases = list(INTENCIONES_JARVIS)
        self.dispositivo = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mtime_cargado = 0.0
        self.val_acc = 0.0
        self._calentado = False

    def _cargar_si_necesario(self) -> bool:
        if not RUTA_MODELO_INTENT.exists():
            return False
        mtime = RUTA_MODELO_INTENT.stat().st_mtime
        if self.modelo is not None and mtime == self.mtime_cargado:
            return True
        try:
            ckpt = torch.load(RUTA_MODELO_INTENT, map_location=self.dispositivo, weights_only=True)
            if ckpt.get("arquitectura") != "JarvisIntentNet_v2_IDF":
                return False
            vocab = dict(ckpt["vocab"])
            idf_map = dict(ckpt["idf_map"])
            clases = list(ckpt.get("clases", INTENCIONES_JARVIS))
            modelo = JarvisIntentNet(
                vocab_size=len(vocab),
                num_clases=len(clases),
                embed_dim=int(ckpt.get("embed_dim", 48)),
                hidden_dim=int(ckpt.get("hidden_dim", 64)),
            ).to(self.dispositivo)
            modelo.load_state_dict(ckpt["state_dict"])
            modelo.eval()
            self.modelo = modelo
            self.vocab = vocab
            self.idf_map = idf_map
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
                idx = torch.tensor([1], dtype=torch.long, device=self.dispositivo)
                off = torch.tensor([0], dtype=torch.long, device=self.dispositivo)
                w = torch.tensor([1.0], dtype=torch.float32, device=self.dispositivo)
                _ = self.modelo(idx, off, w)
            self._calentado = True

    def predecir(self, texto: str) -> dict | None:
        if not self._cargar_si_necesario():
            return None
        t0 = time.perf_counter()
        ids, pesos, ratio_conocidas = codificar_con_pesos(texto, self.vocab, self.idf_map)

        # Protección OOD: si casi ninguna palabra de contenido existe en el vocabulario de comandos,
        # evita disparos falsos por coincidencia casual de letras (ej. "pantalones" vs "pantalla").
        if ratio_conocidas < 0.25:
            lat_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "intencion": "conversacion_general",
                "confianza": 0.92,
                "margen": 0.85,
                "top3": [("conversacion_general", 0.92)],
                "dispositivo": str(self.dispositivo),
                "latencia_ms": round(lat_ms, 2),
                "ood_ratio": round(ratio_conocidas, 2),
            }

        idx_t = torch.tensor(ids, dtype=torch.long, device=self.dispositivo)
        off_t = torch.tensor([0], dtype=torch.long, device=self.dispositivo)
        w_t = torch.tensor(pesos, dtype=torch.float32, device=self.dispositivo)

        with torch.no_grad():
            logits = self.modelo(idx_t, off_t, w_t)
            # Temperatura adaptativa si menos de la mitad de las palabras son conocidas
            temp = 1.65 if ratio_conocidas < 0.50 else 1.0
            probs = torch.softmax(logits / temp, dim=-1)[0].detach().cpu().tolist()

        orden = sorted(enumerate(probs), key=lambda kv: kv[1], reverse=True)
        top1_i, top1_p = orden[0]
        top2_p = orden[1][1] if len(orden) > 1 else 0.0
        lat_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "intencion": self.clases[top1_i],
            "confianza": float(top1_p),
            "margen": float(top1_p - top2_p),
            "top3": [(self.clases[i], round(float(p), 4)) for i, p in orden[:3]],
            "dispositivo": str(self.dispositivo),
            "latencia_ms": round(lat_ms, 2),
            "ood_ratio": round(ratio_conocidas, 2),
        }


_MOTOR_INTENT = _MotorInferenciaIntent()


def calentar_gpu_intent() -> None:
    _MOTOR_INTENT.calentar()


def predecir_intencion_texto(texto: str) -> dict | None:
    return _MOTOR_INTENT.predecir(texto)


def info_intent_net() -> str:
    dev = "GPU CUDA (" + torch.cuda.get_device_name(0) + ")" if torch.cuda.is_available() else "CPU"
    if _MOTOR_INTENT._cargar_si_necesario():
        n_params = sum(p.numel() for p in _MOTOR_INTENT.modelo.parameters())
        return f"PyTorch IntentNet v2 ACTIVA en {dev} ({n_params:,} parámetros | ValAcc: {_MOTOR_INTENT.val_acc*100:.1f}%)"
    return f"PyTorch IntentNet v2 lista en {dev} (ejecuta entrenar_intent_nn.py --entrenar)"
