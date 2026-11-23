# Optimización de capacidad y balanceo de carga en cloud

Artículo académico para el curso Optimización de Operaciones, Universidad Católica de Santa María.

Autores: Franco Salvador Paredes Zamora, Jesús Alberto Briceño Vera y Gonzalo Gilmar Flores Cruz.

## Documento

- `main.tex`: artículo en formato IEEE, con la clase IEEEtran en modo conferencia y dos columnas.
- `secciones/`: introducción, modelo, metodología, resultados, discusión y conclusiones.
- `referencias.bib`: bibliografía; citas y fuentes enlazadas en el PDF.
- `main.pdf`: versión compilada del artículo.
- `figuras/`: gráficos calculados desde las réplicas de la simulación.

En Overleaf, seleccionar `main.tex`, usar pdfLaTeX y recompilar. Se incluyen `IEEEtran.cls` y `IEEEtran.bst` para evitar depender de su disponibilidad local.

Compilación local con TeX Live:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

## Estado del arte breve

`estado_arte.tex` es un documento independiente de dos páginas IEEE, con los mismos autores. Compara seis trabajos sobre simulación cloud, balanceo, selección de alternativas y validez, e incluye una tabla de síntesis. Utiliza `estado_arte_referencias.bib`; el PDF compilado es `estado_arte.pdf`.

Para compilarlo en Overleaf, seleccionar `estado_arte.tex` como documento principal y usar pdfLaTeX. Para regresar al artículo completo, volver a seleccionar `main.tex`.

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error estado_arte.tex
```

## Instalar y ejecutar en Windows

Desde PowerShell en la carpeta del repositorio:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m simulacion.validar
.\.venv\Scripts\python.exe -m simulacion.ejecutar --replicas 30 --workers 4
.\.venv\Scripts\python.exe -m simulacion.analizar
.\.venv\Scripts\python.exe -m simulacion.demostrar
```

No es necesario activar el entorno para utilizar estos comandos. Python 3.11 o posterior. El experimento tarda varios minutos; `--workers 1` reduce el uso de CPU. Para reproducir el artículo, mantener 30 réplicas y los parámetros publicados. La cantidad de procesos no cambia las trazas ni los resultados.

En Linux o macOS, crear el entorno con `python3 -m venv .venv` y sustituir el ejecutable por `.venv/bin/python`.

## Problema y experimento

Se comparan 4, 6 y 8 máquinas virtuales, con Round Robin (RR) y menor cantidad de solicitudes pendientes (MP). Cada VM tiene dos puestos de CPU y una cola FIFO finita. Cuatro hosts físicos limitan la ubicación por CPU y RAM. La memoria se reserva por VM; no se simula consumo dinámico de RAM por petición.

Tres cargas (40/s, 72/s y 40→120→40/s), con y sin fallo de host, producen 36 combinaciones. Treinta réplicas por combinación dan 1.080 ejecuciones principales. La selección minimiza el costo entre alternativas con al menos 99 % de respuestas correctas antes de 10 s y 95 % de respuestas correctas en hasta 2 s, en cada escenario. Los empates de costo se resuelven por el peor p95 medio.

El costo se expresa en unidades monetarias sintéticas, no en dólares ni en tarifas de un proveedor. El modelo no contrata ni utiliza infraestructura cloud real. No implementa autoescalado, migración ni reintentos.

Durante los cinco segundos de detección de un fallo, MP usa la última ocupación conocida de las VMs afectadas; no conoce instantáneamente la caída. Un fallo elimina las solicitudes activas, incluidas las respuestas pendientes del retardo de red.

## Evidencia y reproducibilidad

| Archivo | Evidencia |
|---|---|
| `resultados/replicas.csv` | Métricas de las 1.080 ejecuciones principales |
| `resultados/resumen.csv` | Medias e intervalos puntuales de confianza del 95 % |
| `resultados/seleccion.csv` | Factibilidad y costo de las seis alternativas |
| `resultados/decision.json` | Regla de selección y alternativa elegida |
| `resultados/diferencias_pareadas.csv` | Comparación MP−RR por semilla |
| `resultados/validacion_replicas.csv` | Treinta ejecuciones adicionales de M/M/1 |
| `resultados/validacion.json` | Contraste con los valores teóricos |
| `resultados/metadatos.json` | Versiones, parámetros, tiempo y huellas del código |
| `resultados/pruebas.txt` | Resultado de diez pruebas deterministas |
| `resultados/serie_pico_*.csv` | Series por segundo para demostrar el comportamiento |

El archivo por réplica incluye la huella SHA-256 de la traza. Las alternativas de igual carga y semilla reciben exactamente las mismas llegadas y trabajos. Los intervalos se calculan entre réplicas; no se atribuye independencia a todas las solicitudes de una ejecución.

La validación M/M/1 utiliza parámetros distintos del experimento principal y no certifica el comportamiento de un centro de datos real. La decisión se basa en medias estimadas; los intervalos no son una garantía estadística conjunta ni un SLA comercial.

## Exponer en clase

1. Presentar el problema: ahorrar capacidad sin incumplir servicio.
2. Explicar qué representan host, VM, puesto de CPU y cola.
3. Mostrar la validación contra M/M/1.
4. Abrir la demostración y situarse antes y después del segundo 1.200, cuando sube la demanda.
5. Avanzar al segundo 1.800: falla un host. Comparar colas y capacidad disponible.
6. Mostrar `seleccion.csv` y justificar la configuración de menor costo factible.

La demostración tiene pausa y una barra de tiempo. Reproduce las series obtenidas por el motor SimPy; no cambia en vivo los parámetros ni reemplaza el experimento estadístico. La banda sombreada representa el fallo entre los segundos 1.800 y 1.920. Cinco segundos simulados avanzan por cuadro.

## Archivos de terceros

`IEEEtran.cls` V1.8b y `IEEEtran.bst` V1.14 son de Michael Shell y conservan sus avisos de licencia LPPL y créditos. Se obtuvieron sin modificar de las copias públicas indicadas en `TERCEROS.md`. El formato corresponde a una plantilla IEEE; el trabajo no se presenta como una publicación aceptada por IEEE.


## Acceso y versión del artículo para evaluación

Repositorio: https://github.com/francospz-try/Articulo_Optimizacion_Cloud_Overleaf

Si el repositorio es privado, el enlace del artículo solo funciona para personas
con acceso concedido. Para revisión externa, hacerlo público o invitar a los
evaluadores. Antes de publicarlo, revisar el historial y comprobar que no haya
secretos, archivos personales o información de terceros no autorizada.

La reserva de RAM por host se satisface por la colocación cíclica de las tres
configuraciones evaluadas. El simulador no ejecuta un planificador dinámico de
RAM ni valida de forma general la admisión de nuevas VMs. Tampoco simula
consumo variable de memoria por solicitud.

El código principal de simulación y los resultados históricos se conservan
sin cambios para no invalidar las huellas SHA-256 de `resultados/metadatos.json`.

## Comprobaciones automáticas

`.github/workflows/verificar.yml` ejecuta las pruebas unitarias y de
integridad de los resultados, realiza el contraste M/M/1 y compila el PDF
desde LaTeX. En **Actions**, la ejecución correspondiente al último commit
incluye el PDF actualizado como artefacto `articulo-cloud-pdf`.

**Importante:** `main.pdf` en el árbol del repositorio es una compilación
anterior. Tras editar los archivos `.tex`, utiliza el PDF generado por la
acción o recompila `main.tex` en Overleaf antes de entregarlo. La acción no
rehace las 1.080 ejecuciones, que se conservan como resultados documentados.
