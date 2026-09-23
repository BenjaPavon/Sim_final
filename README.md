# Simulador de colas - Ejercicio 34

Aplicación web para resolver y auditar el ejercicio del cruce ferroviario. El motor está implementado en Python como una simulación estocástica de eventos discretos y la interfaz reproduce la lógica de un vector de estado de planilla: una fila por evento y grupos de columnas para reloj, llegadas, vagón, colas, acumuladores y resultado económico.

La [guía para explicar y defender la aplicación](GUIA_SIMULACION.md) recorre parámetros, llegadas, agenda de eventos, políticas, autos, colas y estadísticas con fórmulas, ejemplos y referencias a funciones y líneas del código.

## Ejecutar

En Windows, haga doble clic en `run.bat` o ejecute:

```powershell
python server.py
```

Luego abra <http://127.0.0.1:8000>. No hace falta instalar paquetes: el proyecto usa solamente la biblioteca estándar de Python y HTML/CSS/JavaScript nativo.

## Que incluye

- Comparación de las políticas A y B por resultado neto promedio de varias réplicas.
- Vector de estado completo, paginado y filtrable por minuto y tipo de evento.
- Columnas `RND`, tiempo entre llegadas y próxima llegada para P1 y P2.
- Calendario de próximas llegadas, fin de traslado y abandonos.
- Estado, posición, recorrido y carga del vagón.
- Cantidad, contenido FIFO y mayor espera de cada cola.
- Acumuladores de llegadas, embarques, entregas, perdidas, viajes y tiempos de espera.
- Ingresos, costos operativos, penalizaciones y resultado neto en cada fila.
- Una columna por auto al final del vector, con sus atributos históricos en cada evento; antes de ingresar se muestra `—`.
- Vistas auxiliares de todos los autos y todos los traslados.
- Parámetros editables para ensayar escenarios distintos.
- Semilla y número de réplicas configurables para reproducir el experimento.

## Modelo de llegadas

Se interpreta «1 auto por minuto» en P1 y «3 autos cada 5 minutos» en P2 como **tasas medias**, no como intervalos exactos ni lotes simultáneos. Esta es una decisión de modelado basada en el apunte de generación de variables de la cátedra; el enunciado del cruce no nombra explícitamente una distribución.

Para cada auto se obtiene un `RND` uniforme en `[0, 1)` y se calcula el tiempo hasta la siguiente llegada mediante la transformada inversa de la exponencial negativa:

`T = -μ × ln(1 - RND)`, con `μ = minutos de referencia / autos esperados`.

La interfaz muestra RND, reloj y tiempos con dos decimales. La generación usa la precisión de `float` y el calendario redondea a nueve decimales; por eso la fórmula puede dar una pequeña diferencia si se reemplaza el RND por su valor visible redondeado.

- P1: `λ = 1` auto/min y `μ = 1` min/auto.
- P2: `λ = 3/5 = 0,6` autos/min y `μ = 5/3 ≈ 1,667` min/auto.

Se programan llegadas individuales. Bajo un proceso de Poisson, el **número** de autos en un intervalo tiene distribución Poisson; el **tiempo entre autos** tiene distribución exponencial negativa. La simulación sigue siendo de eventos discretos porque actualiza el estado solo cuando ocurre un evento.

## Criterios adoptados

1. La primera llegada también se genera con un `RND`; no ocurre obligatoriamente en el minuto 1 o 5.
2. Las colas se atienden FIFO.
3. Un auto puede subir con exactamente 12 minutos de espera. Si no sube, abandona en ese instante antes de superar el limite.
4. En un empate se procesa: arribo del vagón, llegadas de autos, despacho y abandono.
5. La política B comienza en el minuto 0 con un viaje vacío P1 -> P2, coherente con una operación continua.
6. Se incluyen todos los eventos que ocurren exactamente en el minuto 480.
7. El ingreso se registra cuando el auto sube y el costo cuando el viaje comienza. Por eso un viaje iniciado al cierre queda incluido aunque finalice despues.
8. Cada réplica utiliza la misma trayectoria de llegadas para A y B (números aleatorios comunes). Las secuencias de P1 y P2 son independientes entre sí.
9. La tabla, los autos y los traslados muestran la **primera réplica**. La comparación superior presenta **promedios de todas las réplicas** y un intervalo de confianza aproximado del 95 % para la diferencia pareada A − B.

Estos criterios están visibles dentro de la propia aplicación para que la resolución sea defendible y reproducible.

## Interpretación del resultado

Los resultados ya no son cifras fijas del enunciado: dependen de las llegadas aleatorias. Con la semilla y las 100 réplicas predeterminadas, el resultado neto promedio es **$43,06 para A** y **$48,96 para B**. La diferencia media A − B es **−$5,90** y su intervalo aproximado del 95 % es **[−$9,38; −$2,42]**. En ese experimento se favorece **B**, pero el resultado cambia si se modifican la semilla, la cantidad de réplicas o los parámetros.

Con una sola réplica se muestra la diferencia observada, pero no se calcula intervalo de confianza. Si el intervalo de múltiples réplicas incluye cero, la interfaz indica que la ventaja promedio no es concluyente.

## Pruebas

```powershell
python -m unittest discover -s tests -v
node --test tests/test_car_columns.js
```

Las pruebas controlan la fórmula exponencial, reproducibilidad por semilla, igualdad de llegadas entre políticas, conservación de autos, identidad económica, FIFO, espera máxima, orden cronológico, viajes completos de la política A y el desempate en el minuto exacto de abandono.

Las pruebas JavaScript requieren Node.js y Python (configurable mediante `SIM_PYTHON`). Verifican la historia de las columnas individuales y su coincidencia con las colas, carga y contadores del motor; no agregan dependencias para ejecutar la aplicación.

## Estructura

- `simulation.py`: motor de eventos discretos y reglas del sistema.
- `server.py`: servidor HTTP y API `POST /api/simulate`.
- `static/`: interfaz tipo planilla.
- `tests/`: pruebas automaticas del modelo.
