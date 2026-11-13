# Protocolo de pruebas — µPMU v2 (Nucleo-F303K8)
Alejandro Ariza y Laura Sofía Rico — Taller de Potencia 2026-20

## 0. Seguridad
- Los 120 V entran **solo** al borne del ZMPT101B, con cable de ≥ 300 V y fusible de 0,5 A (o el límite de corriente de la fuente).
- La pinza SCT-013 abraza **un solo** conductor. La carga debe ser < 5 A (el canal se satura cerca de 5,8 A).
- Conecta y desconecta todo **con la fuente apagada**. Nunca pongas la punta del osciloscopio en la red.

## 1. Preparación (una vez)
1. En PlatformIO, copia `src/main.cpp` y `platformio.ini`. En `main.cpp` pon tu `VREF` (3V3 medido).
2. Sube el programa con la flecha → (método `mbed`) y pulsa RESET.
3. Copia `capturar_upmu.py` y `uPMU_caracterizacion.ipynb` a una carpeta de trabajo.
4. Prueba la comunicación: `python capturar_upmu.py --puerto COM3` → opción 7 (ayuda). Debe decir `uPMU v2`.

## 2. Verificación (sin red, sin carga)
- Opción 1 (`v`): centro de tensión ≈ 1960 cuentas, centro de corriente ≈ 2048, sin avisos.
- Con GPS: opción 2 (`p`, 10 s). Debe haber 10 periodos de ≈ 1 000 000 µs ± el error del reloj (ppm).

## 3. Ajuste del ZMPT (con red, sin carga) — solo una vez
- Opción 1 (`v`) con la red conectada: min/max de tensión entre ≈ 700 y 3200, sin saturar.
- Si la ganancia es baja (amplitud < ±300 cuentas), gira el potenciómetro **con la fuente apagada** y repite.
- **Después de fijarlo no se vuelve a tocar** (cambia K_V y el desfase).

## 4. Calibración (carga resistiva 50 Ω, rol = calibración)
1. Mide con el multímetro la tensión (V AC) y la corriente (A AC) **durante** la prueba.
2. Opción 3 (`c`): 10 bloques, rol 1 (calibración), resistiva = s, y anota V e I.
3. Repite el paso 2 otra vez para tener más de un punto.

## 5. Validación (otra carga u otro momento, rol = validación)
- Carga resistiva distinta (por ejemplo 100 Ω) y la de 50 Ω otra vez, 15 minutos después.
- Opción 3 (`c`), 10 bloques cada una, rol 2, con sus lecturas del multímetro.

## 6. Estabilidad, frecuencia, ROCOF y sincronía
- Opción 5 (`r`): ráfaga de 5 minutos con la carga de 50 Ω, rol 3. Hace falta el GPS (la coherencia de fase necesita PPS).
- Opción 4 (`f`): 5 bloques libres, para comparar el ángulo con y sin PPS.

## 7. Reporte en tiempo real y latencia
- Pega en `main.cpp` las constantes que entrega el notebook (sección 3), sube de nuevo y ejecuta la opción 6 (`m`, 120 s).
- Durante la prueba conecta y desconecta la carga para ver el cambio en el reporte.

## 8. Perturbaciones (si la fuente es programable)
- Frecuencia 59,5 / 60,5 Hz con `ref_f` = valor de la fuente: FE y comportamiento fuera de 60 Hz.
- Rampa de frecuencia (por ejemplo 0,1 Hz/s): ROCOF medido contra el programado.
- Escalón de magnitud (±10 %): cambio en el reporte.

## 9. Osciloscopio (opcional, mejora la exactitud del ángulo absoluto)
- **Retardo PPS → muestra:** canal 1 en el PPS y canal 2 en PB3 (D13). Valor esperado ≈ 1/4800 s + latencia ≈ 210 µs.
  `CORRECCION_RETARDO_US` = (medido − 208,33 − 2,0) µs. Luego pon `INCERT_RETARDO_US = 0.3`.
- **Fase de un canal:** con un transformador de 12 V AC (ver la sección 4 del notebook). Pon el valor en
  `FASE_I_MEDIDA_OSC_DEG` o en `FASE_V_MEDIDA_OSC_DEG`, y `INCERT_FASE_ABS_DEG = 0.2`.

## 10. Análisis
- Copia la carpeta `datos` junto al notebook, ajusta los parámetros de la primera celda y ejecuta todo (*Run All*).
- Resultados: `resultados/resultados_finales.csv`, `calibracion.csv`, `bloques_analizados.csv` y 6 figuras.
