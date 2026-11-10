#!/usr/bin/env python3
"""
CLI de Agenda y Control Rápido de J.A.R.V.I.S.
Uso:
  jarvis                        -> Muestra en pantalla tu Orden del Día y pendientes
  jarvis hablar                 -> Jarvis lee en voz alta tu Orden del Día
  jarvis escuchar               -> Baja la música al 25% y escucha un comando por voz
  jarvis pendiente "Texto..."   -> Agrega una tarea o pendiente de tus materias
  jarvis reunion "Texto..."     -> Agrega una reunión para hoy
  jarvis listo <ID>             -> Marca como completado el pendiente <ID>
  jarvis limpiar                -> Borra los pendientes que ya completaste
"""

import datetime
import sys
from jarvis_wake import (
    agregar_item_agenda,
    cargar_agenda,
    completar_item_agenda,
    construir_orden_del_dia,
    escuchar_un_comando_directo,
    guardar_agenda,
    hablar_jarvis,
)

DIAS_NOMBRE = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}


def mostrar_resumen_consola() -> None:
    agenda = cargar_agenda()
    hoy_num = datetime.datetime.now().weekday()
    nombre_dia = DIAS_NOMBRE[hoy_num]

    print("=================================================================")
    print(f"  J.A.R.V.I.S. — ORDEN DEL DÍA ({nombre_dia})")
    print("=================================================================")

    clases_hoy = agenda.get("horario_semanal", {}).get(str(hoy_num), [])
    print("\n[HORARIO FIJO DE HOY]:")
    if clases_hoy:
        for c in clases_hoy:
            print(f"  • {c}")
    else:
        print("  • Sin clases fijas registradas para hoy.")

    reuniones = [r for r in agenda.get("reuniones", []) if not r.get("completado", False)]
    print("\n[REUNIONES AGENDADAS]:")
    if reuniones:
        for r in reuniones:
            print(f"  • [{r['id']}] {r['titulo']}")
    else:
        print("  • Sin reuniones adicionales.")

    pendientes = agenda.get("pendientes", [])
    print("\n[TAREAS, MATERIAS Y SESIONES DE ESTUDIO]:")
    if pendientes:
        for p in pendientes:
            estado = "✔" if p.get("completado") else "⏳"
            print(f"  {estado} [{p['id']}] {p['titulo']}")
    else:
        print("  • No hay pendientes registrados.")
    print("=================================================================")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("lista", "status", "agenda"):
        mostrar_resumen_consola()
    elif args[0] in ("hablar", "orden", "brief"):
        hablar_jarvis(construir_orden_del_dia())
    elif args[0] in ("escuchar", "voz"):
        escuchar_un_comando_directo()
    elif args[0] in ("pendiente", "tarea", "add") and len(args) > 1:
        texto = " ".join(args[1:])
        print(agregar_item_agenda("pendiente", texto))
    elif args[0] in ("reunion", "junta") and len(args) > 1:
        texto = " ".join(args[1:])
        print(agregar_item_agenda("reunion", texto))
    elif args[0] in ("listo", "done", "completar") and len(args) > 1 and args[1].isdigit():
        print(completar_item_agenda(int(args[1])))
    elif args[0] == "limpiar":
        agenda = cargar_agenda()
        agenda["pendientes"] = [p for p in agenda.get("pendientes", []) if not p.get("completado", False)]
        agenda["reuniones"] = []
        guardar_agenda(agenda)
        print("[J.A.R.V.I.S.] Pendientes completados y reuniones pasadas eliminados.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
