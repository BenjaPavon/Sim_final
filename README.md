# Simulador de colas - Ejercicio 34

Aplicación web para resolver y auditar el ejercicio del cruce ferroviario. El motor está implementado en Python como una simulación de eventos discretos y la interfaz reproduce la lógica de un vector de estado de planilla: una fila por evento y grupos de columnas para reloj, llegadas, vagón, colas, acumuladores y resultado económico.

## Ejecutar

En Windows, haga doble clic en `run.bat` o ejecute:

```powershell
python server.py
```

Luego abra <http://127.0.0.1:8000>. No hace falta instalar paquetes: el proyecto usa solamente la biblioteca estándar de Python y HTML/CSS/JavaScript nativo.

## Que incluye

- Comparación de las políticas A y B con recomendación por resultado neto.
- Vector de estado completo, paginado y filtrable por minuto y tipo de evento.
- Calendario de próximas llegadas, fin de traslado y abandonos.
- Estado, posición, recorrido y carga del vagón.
- Cantidad, contenido FIFO y mayor espera de cada cola.
- Acumuladores de llegadas, embarques, entregas, perdidas, viajes y tiempos de espera.
- Ingresos, costos operativos, penalizaciones y resultado neto en cada fila.
- Vistas auxiliares de todos los autos y todos los traslados.
- Parámetros editables para ensayar escenarios distintos.

## Criterios adoptados

1. Las llegadas son determinísticas: la primera llegada se produce al completar el intervalo (P1 en el minuto 1 y P2 en el minuto 5).
2. Las colas se atienden FIFO.
3. Un auto puede subir con exactamente 12 minutos de espera. Si no sube, abandona en ese instante antes de superar el limite.
4. En un empate se procesa: arribo del vagón, llegadas de autos, despacho y abandono.
5. La política B comienza en el minuto 0 con un viaje vacío P1 -> P2, coherente con una operación continua.
6. Se incluyen todos los eventos que ocurren exactamente en el minuto 480.
7. El ingreso se registra cuando el auto sube y el costo cuando el viaje comienza. Por eso un viaje iniciado al cierre queda incluido aunque finalice despues.

Estos criterios están visibles dentro de la propia aplicación para que la resolución sea defendible y reproducible.

## Resultado del escenario del enunciado

Con los valores originales, la política A obtiene un resultado neto de **$112**, frente a **$96** de la política B. La política A realiza 96 viajes completos; la B realiza 97 viajes, dos de ellos vacíos. En ambos casos llegan 768 autos y se pierden 272 por superar el límite de espera. Bajo los criterios anteriores, se recomienda la **política A**.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas controlan conservación de autos, identidad económica, FIFO, espera máxima, orden cronológico, viajes completos de la política A y el desempate en el minuto exacto de abandono.

## Estructura

- `simulation.py`: motor de eventos discretos y reglas del sistema.
- `server.py`: servidor HTTP y API `POST /api/simulate`.
- `static/`: interfaz tipo planilla.
- `tests/`: pruebas automaticas del modelo.
