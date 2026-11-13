# -*- coding: utf-8 -*-
"""
capturar_upmu.py  -  registro de datos de la uPMU v2 (Nucleo-F303K8)
Alejandro Ariza y Laura Sofia Rico - Taller de Potencia 2026-20

Uso interactivo (menu):
    python capturar_upmu.py
    python capturar_upmu.py --puerto COM3

Uso directo (sin menu), por ejemplo 10 bloques sincronizados con el PPS:
    python capturar_upmu.py --puerto COM3 --modo c --bloques 10 --prueba R50_cal --rol calibracion --refV 118.4 --refI 2.394 --refang 0

Cada prueba se guarda en la carpeta "datos" (junto a este script) con:
    - lo que mando la placa, sin cambios,
    - los valores de referencia del multimetro (#meta_...),
    - la hora del PC al recibir cada bloque o reporte.
El notebook uPMU_caracterizacion.ipynb lee todos los archivos de esa carpeta.
"""
import argparse
import datetime
import os
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Falta pyserial. Instalalo con:  python -m pip install pyserial")
    sys.exit(1)

BAUD = 115200
CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")

MENU = """
=========== uPMU v2 - registro de datos ===========
 1) Verificar el circuito                         (v)
 2) Prueba del PPS, 10 s                          (p)  -> guarda
 3) Bloques crudos sincronizados con el PPS       (c)  -> guarda
 4) Bloques crudos libres (sin GPS)               (f)  -> guarda
 5) Rafaga continua de bloques crudos             (r)  -> guarda
 6) Medicion de fasores en el MCU, 1 por segundo  (m)  -> guarda
 7) Ayuda del firmware                            (h)
 0) Salir
"""

ROLES = {"1": "calibracion", "2": "validacion", "3": "otra"}


# ---------------------------------------------------------------- puerto
def elegir_puerto(puerto):
    if puerto:
        return puerto
    lista = list(serial.tools.list_ports.comports())
    if not lista:
        print("No hay puertos COM. Conecta el Nucleo por USB.")
        sys.exit(1)
    for k, p in enumerate(lista):
        print(f"  {k}) {p.device}  {p.description}")
    if len(lista) == 1:
        print(f"Usando {lista[0].device}")
        return lista[0].device
    k = input("Numero del puerto: ").strip()
    return lista[int(k)].device


def abrir(puerto, baud):
    s = serial.Serial(puerto, baud, timeout=1)
    time.sleep(0.3)
    s.write(b"x")                 # por si quedo una rafaga o medicion corriendo
    time.sleep(1.5)
    s.reset_input_buffer()
    return s


def leer_hasta(s, fines, max_s, eco=False, guardar=None, marca_pc=False):
    """Lee lineas hasta encontrar una que empiece por alguno de 'fines'. Devuelve la lista de lineas."""
    lineas = []
    t0 = time.time()
    while time.time() - t0 < max_s:
        crudo = s.readline()
        if not crudo:
            continue
        lin = crudo.decode("utf-8", errors="replace").rstrip("\r\n")
        tpc = time.time()
        if marca_pc and lin.startswith("#UPMU"):
            lineas.append(lin)
            lineas.append(f"#t_pc={tpc:.3f}")
        elif marca_pc and lin.startswith("$H"):
            lineas.append(lin + ",t_pc")
        elif marca_pc and lin.startswith("$F"):
            lineas.append(lin + f",{tpc:.3f}")
        else:
            lineas.append(lin)
        if eco:
            print(lin)
        if any(lin.startswith(f) for f in fines):
            return lineas, True
    return lineas, False


def comprobar_firmware(s):
    s.write(b"h")
    lineas, _ = leer_hasta(s, ["  h ="], 3)
    if not any("uPMU v2" in l for l in lineas):
        print("AVISO: la placa no respondio como 'uPMU v2'. Sube el firmware nuevo con PlatformIO (flecha ->).")
        return False
    return True


# ---------------------------------------------------------------- metadatos
ultimo_meta = {}


def preguntar(texto, defecto=""):
    r = input(f"{texto} [{defecto}]: ").strip()
    return r if r else defecto


def pedir_meta(modo):
    global ultimo_meta
    m = dict(ultimo_meta)
    print("\nDatos de la prueba (Enter = repetir el valor entre corchetes)")
    m["prueba"] = preguntar("Nombre corto de la prueba, sin espacios (ej. R50_cal)", m.get("prueba", "prueba"))
    m["prueba"] = m["prueba"].replace(" ", "_")
    rol = preguntar("Rol: 1 = calibracion, 2 = validacion, 3 = otra", {"calibracion": "1", "validacion": "2"}.get(m.get("rol"), "3"))
    m["rol"] = ROLES.get(rol, "otra")
    m["ref_V"] = preguntar("Tension de referencia, multimetro en V AC (Enter si no hay)", m.get("ref_V", ""))
    m["ref_I"] = preguntar("Corriente de referencia, multimetro en A AC (Enter si no hay)", m.get("ref_I", ""))
    res = preguntar("La carga es resistiva pura? (s/n)", "s" if m.get("ref_ang", "") == "0" else "n")
    if res.lower().startswith("s"):
        m["ref_ang"] = "0"
    else:
        m["ref_ang"] = preguntar("Angulo V-I de referencia en grados (Enter si no se conoce)", "" if m.get("ref_ang") == "0" else m.get("ref_ang", ""))
    m["ref_f"] = preguntar("Frecuencia de referencia en Hz (fuente programable o medidor; Enter si no hay)", m.get("ref_f", ""))
    m["carga"] = preguntar("Carga (ej. resistencia 50 ohm)", m.get("carga", ""))
    m["notas"] = preguntar("Notas", "")
    m["modo"] = modo
    ultimo_meta = m
    return m


def nombre_archivo(meta, modo):
    os.makedirs(CARPETA, exist_ok=True)
    sello = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(CARPETA, f"{sello}_{meta.get('prueba', 'prueba')}_{modo}.csv")


def guardar(meta, modo, lineas, puerto):
    ruta = nombre_archivo(meta, modo)
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#meta_version=capturar_upmu 2\n")
        fh.write(f"#meta_fecha={datetime.datetime.now().isoformat(timespec='seconds')}\n")
        fh.write(f"#meta_puerto={puerto}\n")
        for k, v in meta.items():
            fh.write(f"#meta_{k}={v}\n")
        for lin in lineas:
            fh.write(lin + "\n")
    print(f"Guardado: {ruta}")
    return ruta


# ---------------------------------------------------------------- acciones
def verificar(s):
    s.write(b"v")
    leer_hasta(s, ["#FIN_VERIFICACION", "#ERROR"], 6, eco=True)


def ayuda(s):
    s.write(b"h")
    leer_hasta(s, ["  h ="], 3, eco=True)


def prueba_pps(s, meta, puerto):
    print("Prueba del PPS (10 s)...")
    s.write(b"p")
    lineas, ok = leer_hasta(s, ["#FIN_PPS"], 15, eco=True)
    if ok:
        return guardar(meta, "p", lineas, puerto)
    print("No termino la prueba del PPS.")


def bloques(s, meta, puerto, cmd, n):
    todas = []
    for k in range(n):
        s.write(cmd.encode())
        lineas, ok = leer_hasta(s, ["#FIN", "#ERROR"], 8, marca_pc=True)
        todas += lineas
        pps = next((l for l in lineas if l.startswith("#pps=")), "#pps=?")
        estado = "OK" if ok and lineas and lineas[-1].startswith("#FIN") else "FALLO"
        print(f"  bloque {k + 1}/{n}: {estado}  {pps}")
        if not ok:
            break
    return guardar(meta, cmd, todas, puerto)


def continuo(s, meta, puerto, cmd, duracion):
    fin = "#FIN_RAFAGA" if cmd == "r" else "#FIN_MEDICION"
    print(f"Registrando {duracion} s... (Ctrl+C para terminar antes)")
    s.write(cmd.encode())
    todas = []
    t0 = time.time()
    nblq = 0
    try:
        while time.time() - t0 < duracion:
            lineas, _ = leer_hasta(s, ["#FIN", "$L", fin], 3, marca_pc=True)
            todas += lineas
            for lin in lineas:
                if lin == "#FIN":
                    nblq += 1
                    print(f"  bloque {nblq}  ({time.time() - t0:5.1f} s)")
                elif lin.startswith("$F"):
                    c = lin.split(",")
                    try:
                        print(f"  seg {c[1]:>6} | V {float(c[4]):8.2f} V  ang {float(c[5]):8.2f} | "
                              f"I {float(c[6]):7.3f} A  ang {float(c[7]):8.2f} | f {c[8]:>8} Hz | FP {float(c[12]):6.3f}")
                    except (ValueError, IndexError):
                        print("  " + lin)
                elif lin.startswith("$L"):
                    c = lin.split(",")
                    print(f"           latencia total {int(c[2]) / 1000:7.1f} ms")
                elif lin.startswith("#ERROR"):
                    print(lin)
    except KeyboardInterrupt:
        pass
    s.write(b"x")
    lineas, _ = leer_hasta(s, [fin], 6, marca_pc=True)
    todas += lineas
    return guardar(meta, cmd, todas, puerto)


# ---------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description="Registro de datos de la uPMU v2")
    ap.add_argument("--puerto")
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--modo", choices=list("vpcfrmh"))
    ap.add_argument("--bloques", type=int, default=10)
    ap.add_argument("--duracion", type=float, default=60)
    ap.add_argument("--prueba", default="prueba")
    ap.add_argument("--rol", default="otra", choices=["calibracion", "validacion", "otra"])
    ap.add_argument("--refV", default="")
    ap.add_argument("--refI", default="")
    ap.add_argument("--refang", default="")
    ap.add_argument("--reff", default="")
    ap.add_argument("--carga", default="")
    ap.add_argument("--notas", default="")
    a = ap.parse_args()

    puerto = elegir_puerto(a.puerto)
    s = abrir(puerto, a.baud)
    comprobar_firmware(s)

    if a.modo:                                  # uso directo
        meta = dict(prueba=a.prueba, rol=a.rol, ref_V=a.refV, ref_I=a.refI, ref_ang=a.refang,
                    ref_f=a.reff, carga=a.carga, notas=a.notas, modo=a.modo)
        ejecutar(s, a.modo, meta, puerto, a.bloques, a.duracion)
        s.close()
        return

    while True:
        print(MENU)
        op = input("Opcion: ").strip()
        if op == "0":
            break
        modo = {"1": "v", "2": "p", "3": "c", "4": "f", "5": "r", "6": "m", "7": "h"}.get(op)
        if not modo:
            continue
        meta = {}
        n, dur = 10, 60
        if modo in "pcfrm":
            meta = pedir_meta(modo)
            if modo in "cf":
                n = int(preguntar("Numero de bloques", "10"))
            if modo in "rm":
                dur = float(preguntar("Duracion en segundos", "60" if modo == "r" else "120"))
        ejecutar(s, modo, meta, puerto, n, dur)
    s.close()


def ejecutar(s, modo, meta, puerto, n, dur):
    if modo == "v":
        verificar(s)
    elif modo == "h":
        ayuda(s)
    elif modo == "p":
        prueba_pps(s, meta, puerto)
    elif modo in "cf":
        bloques(s, meta, puerto, modo, n)
    elif modo in "rm":
        continuo(s, meta, puerto, modo, dur)


if __name__ == "__main__":
    main()
