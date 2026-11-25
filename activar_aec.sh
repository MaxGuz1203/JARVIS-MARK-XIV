#!/usr/bin/env bash
# Activa WebRTC Acoustic Echo Cancellation (AEC) + Noise Suppression en PipeWire/PulseAudio

if ! command -v pactl >/dev/null 2>&1; then
    exit 0
fi

AEC_SRC=$(pactl list sources short 2>/dev/null | awk '{print $2}' | grep -iE "jarvis_aec|echo[-_]cancel" | grep -v "\.monitor$" | head -n 1)

if [ -z "$AEC_SRC" ]; then
    pactl load-module module-echo-cancel \
        aec_method=webrtc \
        source_name=jarvis_aec_source \
        sink_name=jarvis_aec_sink \
        aec_args="analog_gain_control=0 digital_gain_control=1 noise_suppression=1" \
        >/dev/null 2>&1 \
    || pactl load-module module-echo-cancel \
        aec_method=webrtc \
        source_name=jarvis_aec_source \
        sink_name=jarvis_aec_sink \
        >/dev/null 2>&1 \
    || true
    sleep 0.4
fi

AEC_SRC=$(pactl list sources short 2>/dev/null | awk '{print $2}' | grep -iE "jarvis_aec|echo[-_]cancel" | grep -v "\.monitor$" | head -n 1)
AEC_SNK=$(pactl list sinks short 2>/dev/null | awk '{print $2}' | grep -iE "jarvis_aec|echo[-_]cancel" | head -n 1)

if [ -n "$AEC_SRC" ]; then
    pactl set-default-source "$AEC_SRC" 2>/dev/null || true
    if [ -n "$AEC_SNK" ]; then
        pactl set-default-sink "$AEC_SNK" 2>/dev/null || true
        for input_id in $(pactl list short sink-inputs 2>/dev/null | awk '{print $1}'); do
            pactl move-sink-input "$input_id" "$AEC_SNK" 2>/dev/null || true
        done
    fi
    echo "[OK] Cancelación de eco (AEC) activa -> Mic: $AEC_SRC | Salida: ${AEC_SNK:-default}"
else
    echo "[INFO] AEC de sistema no disponible; operando con sustracción espectral v4."
fi
