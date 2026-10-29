# TODO — Revisión general de pyfwg

Revisión exhaustiva del 2026-10-17 sobre la rama `feature/fwg-v5` (commit `d77c760`, versión 0.4.0 aún sin publicar).

> **Nota de vigencia (2026-10-29):** Este documento ya existía antes de la actualización de pyfwg completada el 2026-10-29. Su contenido refleja el estado de la revisión original y debe contrastarse con el código, las pruebas y la documentación actuales antes de implementar cualquier mejora. Algunos problemas pueden estar ya resueltos y algunas propuestas, prioridades o referencias pueden haber dejado de ser relevantes. Las casillas pendientes no implican que el problema siga vigente.

## Cómo se ha hecho la revisión

- Lectura completa de `pyfwg/` (unas 5.000 líneas), tests, documentación, notebooks, packaging y scripts de publicación.
- `pytest tests --ignore=tests/SS`: **91 tests pasan** (2,4 s). Cobertura de sentencias aproximada: **84 %**, medida con `sys.monitoring` porque no hay `pytest-cov`.
- Scripts de reproducción sin Java para cada bug marcado como *Verificado*. Los fragmentos mínimos están en el [Apéndice A](#apéndice-a--reproducciones-mínimas).
- `python -m build` y `twine check` desde un `git archive` limpio: correctos. Se revisaron el contenido del wheel y su `METADATA`.
- `sphinx-build` de la documentación: 1 aviso. También se revisó el HTML generado.
- `pylint` con un subconjunto de reglas: imports y argumentos sin usar, f-strings sin placeholders y `except` genéricos.
- Contraste con la web y la documentación oficial de FWG: distribuciones, versiones, requisitos y salidas del FWG Engine.
- Entorno: Windows 11, Python 3.14.0, pandas 3.0.5 y Java 25. **No había JAR de FWG disponibles**, así que no se ha ejecutado FWG real.

**Prioridades**

- **P0**: crítico. Produce resultados incorrectos o pérdida de datos, o bloquea la publicación de 0.4.0.
- **P1**: alta.
- **P2**: media.
- **P3**: baja o mejora opcional.

## Resumen

| Sección | P0 | P1 | P2 | P3 | Total |
|---|---:|---:|---:|---:|---:|
| 1. Bugs confirmados (BUG) | 6 | 9 | 5 | – | 20 |
| 2. MorphingIterator (ITE) | – | 4 | 5 | 4 | 13 |
| 3. Robustez y errores (ROB) | – | 5 | 9 | 3 | 17 |
| 4. Integración con el FWG Engine (ENG) | – | 2 | 4 | 3 | 9 |
| 5. Rendimiento (PERF) | – | 1 | 2 | 1 | 4 |
| 6. Diseño de la API (API) | – | 3 | 6 | 6 | 15 |
| 7. Calidad de código (CODE) | – | – | 5 | 5 | 10 |
| 8. Tests (TEST) | – | 4 | 4 | 2 | 10 |
| 9. Documentación (DOC) | 1 | 3 | 5 | 2 | 11 |
| 10. Notebooks y tutoriales (NB) | 1 | 1 | 3 | 1 | 6 |
| 11. Packaging (PKG) | 1 | 2 | 3 | 3 | 9 |
| 12. CI/CD y herramientas (CI) | – | 1 | 2 | 1 | 4 |
| 13. Higiene del repositorio (REPO) | 1 | 3 | 3 | 3 | 10 |
| 14. Licencia y comunidad (LIC) | 1 | – | 1 | 1 | 3 |
| 15. Roadmap de funcionalidades (FEAT) | – | – | – | 3 | 3 |
| **Total** | **11** | **38** | **57** | **38** | **144** |

**Orden recomendado**

1. **Ahora mismo**: REPO-01, el `.crdownload` de 2,4 GB en la raíz del repo.
2. **Antes de publicar 0.4.0**: LIC-01, BUG-01 a BUG-06, PKG-01 (`openpyxl`), NB-01 (rutas personales en los notebooks), DOC-01 (ejemplos inválidos) y DOC-03 (CHANGELOG). Conviene incluir también BUG-07 a BUG-10.
3. **Siguiente iteración**: el resto de P1 (robustez, iterador, procedencia del FWG Engine), TEST-01 a TEST-04 y CI-01.
4. **Después**: el refactor de mantenibilidad (API-03, CODE-05) y el roadmap.

---

## 1. Bugs confirmados

- [ ] **P0 · BUG-01**: `fwg_params` se ignora en casi todos los parámetros.
  Ubicación: `pyfwg/workflow.py:814-851`, con los valores por defecto de las firmas en `workflow.py:1490-1503` y `api.py:279-291`, entre otros.
  Problema: casi todos los argumentos explícitos tienen un valor por defecto distinto de `None` (`fwg_create_ensemble=True`, `fwg_winter_sd_shift=0.0`, `fwg_month_transition_hours=72`, `fwg_interpolation_method_id=0`, `fwg_output_type='EPW'`, las LCZ…). Por eso el `update()` siempre pisa lo que llega en `fwg_params`. Solo se conservan las claves cuyo argumento vale `None` por defecto: modelos, `add_uhi`, versión y opciones del Engine. El CHANGELOG (`CHANGELOG.md:23`) afirma lo contrario.
  *Verificado*: con `fwg_params={'winter_sd_shift': 1.5, 'month_transition_hours': 24, 'create_ensemble': False, 'interpolation_method_id': 2}`, el workflow se configura con 0.0, 72, True y 0.
  *Propuesta*: usar un centinela (`_UNSET = object()`) como valor por defecto en todas las firmas, o `None`, y resolver los valores por defecto después del merge. Así se distingue "no pasado" de "pasado con el valor por defecto". Añadir un test de regresión.

- [ ] **P0 · BUG-02**: los floats llegan tal cual a la línea de comandos de Java.
  Ubicación: `workflow.py:914-925`, `workflow.py:1252`, `workflow.py:1265` y `utils.py:581`.
  Problema: con `fwg_epw_original_lcz=14.0`, `fwg_month_transition_hours=72.0` y `fwg_interpolation_method_id=0.0`, v3 recibe `72.0`, `0.0` y `1:14.0:2.0`, y v4 recibe `-smooth_hours=72.0` y `-uhi=true:14.0:2.0`. pandas convierte a `float64` toda columna numérica con huecos (NaN), así que el flujo Excel → `MorphingIterator` lo provoca de forma natural.
  *Verificado*.
  *Propuesta*: normalizar los tipos al construir `final_fwg_params`: `_as_int_id()` para los enteros, `float()` para los shifts y booleanos estrictos (BUG-03). Rechazar valores no enteros como 14.5 y convertir también en `load_runs_from_excel`.

- [ ] **P0 · BUG-03**: los booleanos se interpretan de forma distinta según la versión, y el UHI puede activarse o desactivarse al revés.
  Ubicación: `workflow.py:916` y `workflow.py:924` evalúan la veracidad (truthiness). En cambio, `workflow.py:1250-1254` compara `str(x).lower() == 'true'`. Ver también `workflow.py:1262`, `1266` y `1268`.
  Problema: `fwg_add_uhi=1` genera `-uhi=false` en v4. `fwg_add_uhi='False'` (texto típico de Excel) aplica el UHI en v3 (`1:14:1`).
  *Verificado*.
  *Propuesta*: una única función `_to_bool()` que acepte `bool`, `numpy.bool_`, 0/1 y "true"/"false", y que rechace el resto. Usarla en todos los flags y también en la validación.

- [ ] **P0 · BUG-04**: `sanitize_epw_minutes` corrompe las cabeceras que no están en UTF-8.
  Ubicación: `utils.py:1010`.
  Problema: lee con `encoding='utf-8', errors='ignore'` y reescribe en UTF-8, así que elimina los bytes Latin-1, frecuentes en EPW ("Málaga", "São Paulo", "Zürich"). Muchos EPW usan el minuto 60: los 4 de ejemplo lo tienen en sus 8.760 registros. Por eso el fichero se reescribe casi siempre. Afecta a la copia que recibe FWG y previsiblemente a la cabecera de las salidas.
  *Verificado*: `LOCATION,M\xe1laga,…` pasa a `LOCATION,Mlaga,…`.
  *Propuesta*: procesar en binario o con `latin-1`, que conserva cada byte. Tocar solo las líneas posteriores a las 8 de cabecera y conservar los finales de línea. Añadir un test con una cabecera Latin-1.

- [ ] **P0 · BUG-05**: el iterador da un falso "Definitive file overwrite" cuando las ejecuciones escriben en carpetas distintas.
  Ubicación: `iterator.py:473-507`.
  Problema: la simulación de nombres ignora `final_output_dir`. Como `raise_on_overwrite=True` es el valor por defecto, se bloquean estudios válidos.
  *Verificado*: dos filas idénticas salvo `final_output_dir` (`out_a` y `out_b`) lanzan `ValueError`.
  *Propuesta*: comparar rutas absolutas normalizadas (`os.path.normcase(os.path.abspath(...))`). Mejor aún, aplicar la solución de BUG-06.

- [ ] **P0 · BUG-06**: el iterador solo valida el patrón de la primera fila y no detecta colisiones reales.
  Ubicación: `iterator.py:425-428` y `iterator.py:491-495`.
  Problema: cada fila puede tener su propio `output_filename_pattern`, pero se usa `iloc[0]` para todas. Además, cuando una fila tiene varios EPW, se simula un único nombre por fila, con la lista de categorías, en lugar de uno por fichero.
  *Verificado*: las filas 2 y 3, con el mismo patrón y distinto GCM, escriben exactamente los mismos ficheros y no se avisa.
  *Propuesta*: preparar primero los workflows y comprobar las colisiones sobre sus `rename_plan` reales, que ya se calculan por fichero, escenario y año, usando las rutas absolutas de destino. Así se elimina la simulación paralela.

- [ ] **P1 · BUG-07**: `_apply_defaults` falla con listas cuando hay un valor por defecto personalizado.
  Ubicación: `iterator.py:298-300`.
  Problema: `pd.isnull(['A', 'B'])` devuelve un array, y se lanza `ValueError: The truth value of an array … is ambiguous`.
  *Verificado*: con `set_default_values(fwg_gcms=[...])` y una columna `fwg_gcms` con listas de 2 o más elementos.
  *Propuesta*: un helper `_is_missing(x)` que solo considere NA los valores escalares, por ejemplo `pd.api.types.is_scalar(x) and pd.isna(x)`.

- [ ] **P1 · BUG-08**: importar pyfwg reconfigura el logging de la aplicación.
  Ubicación: `pyfwg/__init__.py:18-66`.
  Problema: borra todos los handlers del logger raíz (`logger.handlers.clear()`) y fija su nivel a INFO. Una librería no debe tocar el logger raíz. Además, el comentario de las líneas 31-33 contradice al código: tras el `clear()`, la condición siempre se cumple.
  *Verificado*: el handler de una aplicación desaparece tras `import pyfwg`, y un nivel WARNING pasa a INFO.
  *Propuesta*: `logging.getLogger(__name__)` en cada módulo, un `NullHandler` en `pyfwg`, y una función opcional `pyfwg.enable_console_logging(level=..., color=True)` para notebooks.

- [ ] **P1 · BUG-09**: `uhi_morph(raise_on_error=False)` sigue lanzando excepciones.
  Ubicación: `utils.py:610-611`.
  Problema: el `except` relanza siempre. El comportamiento documentado (`utils.py:501-504`) solo existe en el código comentado de `utils.py:612-628`.
  *Verificado* con `CalledProcessError`.
  *Propuesta*: implementar la rama `raise_on_error=False` (registrar el error y devolver `None` o un resultado), o eliminar el parámetro.

- [ ] **P1 · BUG-10**: `MorphingWorkflowCordex` acepta JAR de Europe v1/v2 y construye para ellos un comando del FWG Engine.
  Ubicación: `utils.py:401-403` y `workflow.py:676`.
  Problema: `get_fwg_cli_style(..., 'cordex')` siempre devuelve `engine`, y `_check_jar_matches_workflow` da 'europe' por compatible.
  *Verificado*: `FutureWeatherGenerator_Europe_v2.0.2.jar` produce una configuración válida con `cli_style='engine'`, que fallará en Java.
  *Propuesta*: exigir el estilo `engine` en el workflow CORDEX (Europe v3 o superior). Si no, marcar la configuración como inválida con el mensaje "usa MorphingWorkflowEurope".

- [ ] **P1 · BUG-11**: el estado queda inconsistente si el patrón de salida no es válido.
  Ubicación: `workflow.py:934-959`.
  Problema: `self.inputs` se actualiza, e `is_config_valid` sigue en `True`, antes de lanzar el `ValueError` del patrón.
  *Verificado*: tras capturar la excepción, `execute_morphing()` no se bloquea. Simplemente salta todos los ficheros.
  *Propuesta*: validar el patrón al principio y poner `is_config_valid = False` ante cualquier error.

- [ ] **P1 · BUG-12**: la validación del patrón de salida es frágil.
  Ubicación: `workflow.py:958`, `workflow.py:999`, `workflow.py:1018` e `iterator.py:428`.
  Problema: rechaza `{year:04d}`, que es un formato válido. Un `{}` posicional produce un plan vacío con "ERROR … ['']". Los accesos a atributos o índices (`{fwg_gcms[0]}`) se tratan como claves inexistentes.
  *Verificado*.
  *Propuesta*: extraer los campos con `string.Formatter().parse()` y capturar `KeyError`, `IndexError` y `ValueError` de `format()` con un mensaje claro.

- [ ] **P1 · BUG-13**: no se detectan colisiones de destino dentro de un mismo workflow.
  Ubicación: `workflow.py:984-1026`.
  Problema: dos EPW con el mismo nombre en carpetas distintas, o un patrón sin una categoría que los distinga, generan los mismos destinos, y el segundo sobrescribe al primero. Además, ambos comparten la carpeta temporal `temp_base_dir/<basename>` (`workflow.py:1102` y `api.py:48`).
  *Verificado*: 16 destinos, de los que solo 8 son únicos, sin ningún aviso.
  *Propuesta*: detectar los duplicados en `rename_plan` (error o aviso) y usar carpetas temporales únicas, con un índice o un hash de la ruta absoluta.

- [ ] **P1 · BUG-14**: las listas se formatean como `['CanESM5']` en los nombres de fichero.
  Ubicación: `workflow.py:979-1018`.
  Problema: un patrón con `{fwg_gcms}`, que es lo que sugiere el propio aviso del iterador, produce `Seville_ssp126_2050_['CanESM5'].epw`.
  *Verificado*.
  *Propuesta*: formatear las listas como `CanESM5-MIROC6` (o de forma configurable) y sanear los caracteres no válidos en nombres de fichero (`<>:"/\|?*` y espacios).

- [ ] **P1 · BUG-15**: un valor numérico pasado como texto rompe la validación con `TypeError`.
  Ubicación: `workflow.py:427-443`.
  Problema: `fwg_winter_sd_shift='0.5'` lanza `TypeError: '<=' not supported…` en lugar de un mensaje de validación.
  *Verificado*.
  *Propuesta*: convertir el tipo y, si no es posible, dar un mensaje claro ("'fwg_winter_sd_shift' debe ser numérico").

- [ ] **P2 · BUG-16**: `fwg_output_type` distingue mayúsculas y falla con valores que no son texto.
  Ubicación: `workflow.py:501-509`, frente a `workflow.py:163`.
  Problema: 'epw' se rechaza, pero las extensiones se calculan con `.upper()`. Un valor que no es `str` provoca `AttributeError` al llamar a `.upper()`.
  *Propuesta*: normalizar con `_normalize_option()` antes de validar.

- [ ] **P2 · BUG-17**: las claves desconocidas de `fwg_params`, o con el prefijo `fwg_`, se ignoran en silencio.
  Ubicación: `workflow.py:814-851`.
  Problema: `{'winter_shift': 1}` o `{'fwg_summer_sd_shift': 1}` se aceptan sin aviso y no tienen ningún efecto.
  *Verificado*.
  *Propuesta*: validar las claves contra la lista de parámetros conocidos. Aceptar ambos formatos (`x` y `fwg_x`) o avisar.

- [ ] **P2 · BUG-18**: CORDEX acepta la interpolación 'BI', aunque su docstring dice que no se aplica.
  Ubicación: `workflow.py:1984-1987`, frente a `workflow.py:462-467`.
  *Verificado*: `is_config_valid=True`.
  *Propuesta*: una regla específica para los dominios CORDEX, como error o como aviso.

- [ ] **P2 · BUG-19**: ejecuciones con el mismo EPW reutilizan carpetas temporales con restos de ejecuciones anteriores.
  Ubicación: `workflow.py:1102-1103` y `api.py:48-49`.
  Problema: con `delete_temp_files=False`, o tras un fallo, una ejecución posterior encuentra ficheros antiguos, y `_process_generated_files` puede moverlos como si fueran nuevos. La documentación oficial del Engine advierte de que un fichero antiguo en disco no demuestra que la ejecución actual haya terminado.
  *Propuesta*: usar una carpeta temporal nueva por ejecución, por ejemplo con `tempfile.mkdtemp(dir=temp_base_dir)`.

- [ ] **P2 · BUG-20**: la API simple da un error engañoso cuando falta un EPW, y no acepta `pathlib.Path`.
  Ubicación: `api.py:351` y `api.py:361-363`, con sus equivalentes en `api.py:653`, `662`, `791` y `794`.
  Problema: un fichero inexistente se descarta en silencio y luego salta `RuntimeError: Please run map_categories() first`, aunque el usuario nunca ha llamado a `map_categories`. Con un `Path` se produce `TypeError: 'WindowsPath' object is not iterable`.
  *Verificado*.
  *Propuesta*: lanzar `FileNotFoundError` con la lista de rutas que faltan, y aceptar `os.PathLike` (y listas de ellos) en todas las funciones.

## 2. MorphingIterator

- [ ] **P1 · ITE-01**: una columna extra en el DataFrame hace que su fila se descarte en silencio.
  Ubicación: `iterator.py:542-567`.
  Problema: una columna como `notes` o `run_id`, o un nombre mal escrito como `fwg_gcm`, llega a `configure_and_preview(**run_params)` y provoca un `TypeError`. Ese error solo se registra en el log, y la fila no se ejecuta.
  *Verificado*: 0 workflows preparados.
  *Propuesta*: validar las columnas al principio, con un error claro y sugerencias (`difflib.get_close_matches`). Permitir columnas de metadatos (por ejemplo con el prefijo `meta_`) y que se puedan usar como placeholders.

- [ ] **P1 · ITE-02**: los fallos de preparación solo aparecen en el log, y `prepared_workflows` pierde la correspondencia con las filas.
  Ubicación: `iterator.py:566-567` e `iterator.py:606-607`.
  Problema: si falla una fila, la "Run N" de la ejecución deja de coincidir con la fila N del DataFrame.
  *Verificado*: se prepara 1 de 2 filas, sin ninguna referencia a su índice.
  *Propuesta*: guardar `run_index` en cada workflow, añadir columnas `status` y `error` a `morphing_workflows_plan_df` y ofrecer la opción `raise_on_error`.

- [ ] **P1 · ITE-03**: la validación de capa 1 da falsos positivos y se salta columnas.
  Ubicación: `iterator.py:434-452`.
  Problema: `temp_base_dir`, `delete_temp_files`, `fwg_show_tool_output`, `run_incomplete_files` y `fwg_use_multithreading` no afectan ni al nombre ni al contenido de las salidas, pero se avisa si varían. A la vez, las columnas con diccionarios (`fwg_params`, `fwg_extra_args`, `scenario_mapping`) se ignoran en silencio, porque no son hashables.
  *Propuesta*: una lista explícita de las columnas que afectan al resultado, y hashear los diccionarios con `json.dumps(..., sort_keys=True)`.

- [ ] **P1 · ITE-04**: el iterador exige una estrategia de mapeo.
  Ubicación: `iterator.py:381` y `workflow.py:290-291`.
  Problema: sin `input_filename_pattern` ni `keyword_mapping`, se lanza `ValueError`, incluso cuando solo se quieren variar parámetros sobre un EPW.
  *Verificado*.
  *Propuesta*: permitir mapear sin reglas (con categorías vacías) y ofrecer el placeholder `{epw_name}` (API-04).

- [ ] **P2 · ITE-05**: `set_default_values` reemplaza los valores anteriores en lugar de acumularlos.
  Ubicación: `iterator.py:180`.
  Problema: dos llamadas seguidas pierden los valores de la primera.
  *Propuesta*: hacer merge (y añadir `reset_default_values()`), o documentarlo.

- [ ] **P2 · ITE-06**: `run_morphing_workflows` no devuelve nada ni muestra un resumen.
  Ubicación: `iterator.py:571-634`.
  *Propuesta*: devolver un DataFrame con estado, ficheros creados, duración y error de cada fila, y registrar un resumen final ("12/14 ejecuciones correctas").

- [ ] **P2 · ITE-07**: mensaje engañoso cuando han fallado todas las preparaciones.
  Ubicación: `iterator.py:600-601`.
  Problema: dice "Please run generate_morphing_workflows() first" aunque ya se ha ejecutado.
  *Propuesta*: distinguir entre "no ejecutado" y "ninguna fila válida".

- [ ] **P2 · ITE-08**: `run_morphing_workflows(show_tool_output=...)` modifica el estado de los workflows de forma permanente.
  Ubicación: `iterator.py:614-615`.
  *Propuesta*: aplicar la opción solo durante esa ejecución.

- [ ] **P2 · ITE-09**: las columnas obligatorias no se validan.
  Problema: si falta `output_filename_pattern`, salta un `KeyError` en `iterator.py:425`. Si faltan `final_output_dir` o `fwg_jar_path`, cada fila falla en silencio.
  *Propuesta*: comprobarlas al principio con un mensaje claro.

- [ ] **P3 · ITE-10**: las columnas `cat_*` tienen un orden no determinista.
  Ubicación: `iterator.py:396-400`, que usa un `set`.
  *Propuesta*: usar `sorted()`.

- [ ] **P3 · ITE-11**: un `epw_paths` vacío (NaN) o de tipo `PathLike` en una fila no se gestiona.
  Ubicación: `iterator.py:372-373` e `iterator.py:553`.

- [ ] **P3 · ITE-12**: el tipado de `set_default_values` no coincide con el de los workflows.
  Ubicación: `iterator.py:111-114`.
  Problema: declara `Optional[int]` para la interpolación, el ajuste solar y el modelo de difusa, mientras los workflows aceptan `Union[int, str]`.

- [ ] **P3 · ITE-13**: detalles del mensaje de colisiones.
  Problema: siempre añade la extensión `.epw` (`iterator.py:515`), aunque la salida sea `.met` o `.csv`. Además, la simulación usa `ALL_POSSIBLE_YEARS` y los escenarios de la clase (`iterator.py:489-491`), sin tener en cuenta `fwg_scenarios`, `fwg_timeframes` ni la región del JAR. Queda resuelto con BUG-06.

## 3. Robustez y manejo de errores

- [ ] **P1 · ROB-01**: un Java ausente o un JAR inexistente se detectan demasiado tarde.
  Ubicación: `workflow.py:857-884` y `workflow.py:1194-1207`.
  Problema: un JAR que no existe da una configuración válida (*verificado*). El `FileNotFoundError` que lanza `subprocess` cuando `java` no está en el PATH no se captura en `_execute_single_morph`, así que aborta todo `execute_morphing`.
  *Propuesta*: en `configure_and_preview`, comprobar `os.path.isfile(fwg_jar_path)` y `shutil.which('java')`. Durante la ejecución, capturar `FileNotFoundError` y `OSError` con un mensaje claro. Añadir el parámetro `java_path` y soporte de `JAVA_HOME`.

- [ ] **P1 · ROB-02**: no se comprueba la versión de Java.
  Problema: según la documentación oficial, el FWG Engine requiere Java 17 o superior, y el README solo pide que `java` esté en el PATH.
  *Propuesta*: leer `java -version` una vez, guardar el resultado en caché y avisar o dar error según la versión de FWG.

- [ ] **P1 · ROB-03**: la salida del proceso se decodifica con la codificación local.
  Ubicación: `workflow.py:1195` y `utils.py:607`.
  Problema: `text=True` sin `encoding` usa la codificación local (cp1252 en Windows). Si la salida de Java no viene en esa codificación, puede producirse un `UnicodeDecodeError` que no se captura, o texto corrupto.
  *Propuesta*: usar `encoding='utf-8', errors='replace'`.

- [ ] **P1 · ROB-04**: se considera éxito cualquier código de salida 0.
  Ubicación: `workflow.py:1106-1114`.
  Problema: no se comprueba que existan las salidas esperadas. Con el Engine, es el run manifest quien indica el estado final (ENG-01 y ENG-03).
  *Propuesta*: verificar los ficheros esperados y tratar "0 ficheros movidos" como fallo.

- [ ] **P1 · ROB-05**: la salida de la herramienta se pierde.
  Ubicación: `workflow.py:1187-1199`.
  Problema: cuando no hay error, la salida se descarta. Con `show_tool_output=True` se muestra pero no se guarda, así que no queda nada para diagnosticar después.
  *Propuesta*: escribir siempre stdout y stderr en un log por ejecución (`<temp>/fwg_tool.log`), y mostrarlo además por consola si se pide.

- [ ] **P2 · ROB-06**: los timeouts son fijos.
  Ubicación: `workflow.py:64` (600 s y 3.600 s) y `utils.py:607` (300 s).
  Problema: un ensemble de 23 GCM en una máquina lenta puede superar los 600 s.
  *Propuesta*: parametrizarlo (`fwg_timeout`), donde `None` signifique sin límite.

- [ ] **P2 · ROB-07**: `shutil.move` sobrescribe destinos sin avisar y falla con subcarpetas.
  Ubicación: `workflow.py:1413` y `api.py:95`.
  Problema: sobrescribe destinos existentes en silencio, y falla con `FileNotFoundError` si el patrón incluye subcarpetas (`{city}/{ssp}_{year}`).
  *Propuesta*: crear la carpeta con `os.makedirs(os.path.dirname(...), exist_ok=True)` y añadir una política `overwrite='error'|'skip'|'overwrite'`.

- [ ] **P2 · ROB-08**: `_robust_rmtree` no borra todo lo que debería.
  Ubicación: `utils.py:120-145`.
  Problema: no gestiona ficheros de solo lectura en Windows y, tras agotar los reintentos, solo registra el error. Tampoco se borra nunca `temp_base_dir`, que queda vacío en el directorio de trabajo (`./morphing_temp_results`).
  *Propuesta*: usar `onexc`/`onerror` con `os.chmod` y borrar la carpeta base cuando quede vacía, o crear por defecto un temporal con `tempfile.mkdtemp(prefix='pyfwg_')`.

- [ ] **P2 · ROB-09**: `map_categories` acepta directorios y no normaliza las rutas.
  Ubicación: `workflow.py:303` y `workflow.py:374-380`.
  Problema: acepta directorios (usa `os.path.exists`) y cualquier extensión. Las claves no son rutas absolutas, aunque el docstring dice que sí (`workflow.py:182-184`), así que el mismo fichero pasado con ruta relativa y absoluta se procesa dos veces.
  *Propuesta*: usar `os.path.isfile`, normalizar a ruta absoluta y avisar si el fichero no es `.epw`.

- [ ] **P2 · ROB-10**: la búsqueda por palabras clave es ambigua.
  Ubicación: `workflow.py:350-359`.
  Problema: busca subcadenas en el nombre completo, incluida la extensión. La palabra 'epw' casa con todos los ficheros (*verificado*), 'type-1' casa con 'type-10', y gana la primera regla según el orden del diccionario.
  *Propuesta*: buscar solo en el nombre sin extensión, ofrecer coincidencia por token o por regex, y avisar de las ambigüedades.

- [ ] **P2 · ROB-11**: `input_filename_pattern` no se valida.
  Ubicación: `workflow.py:316`.
  *Propuesta*: compilar la regex una sola vez y dar un error claro si no es válida o no tiene grupos con nombre. Avisar cuando un valor extraído no aparece en `keyword_mapping`.

- [ ] **P2 · ROB-12**: `check_lcz_availability` depende de un texto concreto de la herramienta.
  Ubicación: `utils.py:715-733`.
  Problema: busca el texto en inglés "The LCZs available are:", y devuelve tres tipos distintos de resultado (`True`, `dict` o `False`).
  *Propuesta*: devolver un dataclass con el resultado, tolerar variantes del formato y probar con salidas reales capturadas de v3 y v4.

- [ ] **P2 · ROB-13**: `load_runs_from_excel` es frágil.
  Ubicación: `utils.py:985-991`.
  Problema: no tolera espacios al principio de la celda. Un literal mal formado lanza `SyntaxError` sin indicar la fila ni la columna (*verificado*). Tampoco convierte 14.0 en 14 ni "TRUE"/"FALSE" en booleanos.
  *Propuesta*: hacer `strip()`, capturar los errores indicando la fila y la columna, y convertir los tipos de cada columna según la especificación del parámetro (API-03).

- [ ] **P2 · ROB-14**: `copy_tutorials` tiene varios problemas.
  Ubicación: `utils.py:44-118`.
  Problema:
  - Si no encuentra el paquete, registra un error y sigue, en lugar de lanzar una excepción.
  - En una instalación editable copia también `.ipynb_checkpoints` y los restos `morphing_temp_results*` (*verificado*).
  - No permite controlar la sobrescritura.
  - `pyfwg.tutorials` no tiene `__init__.py`, así que es un *namespace package*. `importlib.resources.files()` solo los admite desde Python 3.10, por lo que en Python 3.9, todavía declarado compatible, probablemente falla. No se ha podido comprobar: aquí solo hay Python 3.14.

  *Propuesta*: añadir `__init__.py` o subir el mínimo a Python 3.10. Ampliar los patrones ignorados, añadir el parámetro `overwrite` y devolver la ruta de destino.

- [ ] **P3 · ROB-15**: `detect_fwg_version` se basa en el nombre del fichero.
  Ubicación: `utils.py:322`.
  Problema: la regex `v(\d+)\.` puede casar con otros textos del nombre.
  *Propuesta*: para los JAR antiguos, intentar leer también `META-INF/MANIFEST.MF`.

- [ ] **P3 · ROB-16**: `int(float(...))` trunca sin avisar 72.5 h a 72.
  Ubicación: `workflow.py:1309`.
  *Propuesta*: validar que el valor sea entero.

- [ ] **P3 · ROB-17**: `get_available_lczs` indexa los resultados por nombre de fichero.
  Ubicación: `utils.py:899-935`.
  Problema: dos EPW con el mismo nombre en carpetas distintas colisionan. Además, `num_files` cuenta mal las tuplas (`utils.py:888`).

## 4. Integración con el FWG Engine

Según la web oficial, consultada el 2026-10-17: Engine v1.1.0, esquema de recursos 1.4, Java 17+, Global v5.2.0, Europe v3.2.0, distribuciones regionales v1.2.0 y Portugal v0.1.4.

- [ ] **P1 · ENG-01**: localizar las salidas a través del run manifest.
  Problema: la documentación oficial dice: "Exact filenames are distribution- and configuration-aware. The run manifest is the reliable index of generated artifacts." Hoy pyfwg localiza los ficheros buscando subcadenas como `ssp245_2050` en los nombres (`workflow.py:1389-1399` y `api.py:85-91`).
  *Propuesta*: leer el run manifest de `metadata/`, que da escenario, periodo, modelo, ruta, checksum y estado. Mantener la búsqueda por nombre solo como alternativa para v3 y v4.

- [ ] **P1 · ENG-02**: conservar la procedencia de los resultados.
  Problema: la documentación oficial recomienda archivar junto a los resultados el run manifest, los scenario manifests, los informes y los checksums. Con `delete_temp_files=True`, que es el valor por defecto, pyfwg los borra (`workflow.py:1112-1114` y `api.py:98-100`).
  *Propuesta*: añadir la opción `keep_provenance=True`, activada por defecto con el Engine, que mueva `reports/`, `metadata/` y `logs/` a `<final_output_dir>/<epw>_fwg_provenance/`. Avisar al usar `fwg_output_profile='MINIMAL'`.

- [ ] **P2 · ENG-03**: decidir el éxito o el fallo de cada caso según el estado de terminación de los manifests, no solo según el código de salida.

- [ ] **P2 · ENG-04**: ofrecer una opción para recuperar el *present-day control* y la línea base corregida por SolarQC, con sus propios placeholders. Hoy se quedan en la carpeta temporal.

- [ ] **P2 · ENG-05**: FWG Portugal v0.1.4 no está soportada.
  Problema: es una distribución oficial (WRF, escenarios SSP, periodos 2055 y 2090). `detect_fwg_tool` la identifica como 'portugal', pero `ALL_POSSIBLE_YEARS=[2050, 2080]` no sirve para ella.
  *Propuesta*: soportarla con un workflow propio, o documentar que no está soportada.

- [ ] **P2 · ENG-06**: mantener las constantes sincronizadas con FWG.
  Estado actual: a 2026-10-17 coinciden con la web oficial: los 23 GCM de CMIP6 Global, los 7 productos de EUR-11, y los 9 dominios CORDEX con sus pares y escenarios.
  *Propuesta*: una lista de comprobaciones de mantenimiento por cada versión de FWG, y un aviso si el `engine_version` del JAR es mayor que la última versión probada.

- [ ] **P3 · ENG-07**: investigar si la CLI admite varios EPW por invocación, con el layout `PER_RUN_ORGANIZED`, que según la documentación es el valor por defecto para lotes multi-EPW. Así se amortizarían el arranque de la JVM y la descompresión de los datos.

- [ ] **P3 · ENG-08**: a largo plazo, un backend Java opcional.
  Problema: la guía oficial de desarrollo dice que las integraciones deberían usar `GenerationService` (la API Java) en lugar de lanzar la CLI.
  *Propuesta*: evaluar un backend opcional con JPype o Py4J, con progreso, cancelación y resultados tipados.

- [ ] **P3 · ENG-09**: interpretar los códigos de error estables del Engine para dar mensajes más claros.

## 5. Rendimiento

- [ ] **P1 · PERF-01**: la comprobación de LCZ es muy costosa.
  Ubicación: `workflow.py:1069-1097`, `api.py:51-72` y `utils.py:675-699`.
  Problema: ejecuta un `UHI_Morph` completo por cada EPW y cada ejecución. En el iterador, el mismo EPW se vuelve a validar en cada fila.
  *Propuesta*: obtener una sola vez las LCZ disponibles de cada combinación de EPW y JAR (con la sonda LCZ 0), guardarlas en caché y validar los pares localmente.

- [ ] **P2 · PERF-02**: ejecución paralela opcional (`max_workers`) de los EPW o las filas independientes, avisando del consumo de RAM y del multihilo propio de FWG.

- [ ] **P2 · PERF-03**: reutilizar por defecto `fwg_model_unzipped_folder` en los lotes del Engine (por ejemplo, dentro de `temp_base_dir`) para no descomprimir los datos de los modelos en cada ejecución.

- [ ] **P3 · PERF-04**: poder reanudar lotes con `skip_existing=True`, sin repetir las ejecuciones cuyos destinos ya existen.

## 6. Diseño de la API

- [ ] **P1 · API-01**: devolver resultados estructurados.
  Problema: `execute_morphing()` devuelve `None` (`workflow.py:1030`). `morph_epw_*` devuelve solo las rutas creadas, y los fallos solo quedan en el log. `run_morphing_workflows()` devuelve `None`.
  *Propuesta*: un dataclass `MorphingResult` con los ficheros creados por EPW, escenario y año, los fallos con su motivo, el comando, la duración y las rutas de log. Para no romper compatibilidad, mantener la lista en la API simple o añadir `return_result=True`.

- [ ] **P1 · API-02**: excepciones propias y errores de validación accesibles.
  Problema: el `ValueError` de la API dice "check the warnings in the log above" (`api.py:39`), algo inútil si el logging está desactivado.
  *Propuesta*: excepciones `PyFWGError`, `ConfigurationError`, `FWGExecutionError` y `LCZNotAvailableError`, y un atributo `workflow.validation_errors: list[str]`.

- [ ] **P1 · API-03**: una fuente única para los parámetros.
  Problema: la lista de unos 35 parámetros de FWG está duplicada en unos 10 sitios: las 3 funciones de `api.py`, los 3 `configure_and_preview`, `_configure_and_preview_base` (firma y diccionario `overrides`), `set_default_values` (firma y `provided_args`) y `get_fwg_parameters_info`. Los rangos de validación (`workflow.py:427-443`) también duplican los de `utils.py:1069-1133`.
  *Propuesta*: un registro declarativo, por ejemplo un dataclass `ParamSpec` con nombre, tipo, valor por defecto, rango o valores permitidos, versiones y distribuciones a las que se aplica, y descripción. De él se generarían la validación, la conversión de tipos, la documentación, la plantilla de Excel y `get_fwg_parameters_info`. Las firmas explícitas pueden mantenerse para el IDE, o generarse con `__signature__`.

- [ ] **P2 · API-04**: placeholders integrados.
  - `{epw_name}`: nombre del EPW original sin extensión.
  - `{model}`: salidas por modelo con `create_ensemble=False`. Hoy solo se conserva la primera (`workflow.py:907-911`), aunque la documentación oficial contempla procesar varios modelos por separado.
  - `{run_id}` y las columnas de metadatos del iterador.

- [ ] **P2 · API-05**: control de la verbosidad.
  Problema: las 14 llamadas a `print()` de `workflow.py` no se pueden silenciar. Con un iterador de 100 filas inundan la salida.
  *Propuesta*: un parámetro `verbose` o usar logging, y un método `workflow.plan_dataframe()` que devuelva el plan de forma estructurada.

- [ ] **P2 · API-06**: `dry_run=True` en las funciones de la API simple, y una opción `overwrite` (ROB-07).

- [ ] **P2 · API-07**: nombres coherentes.
  Problema:
  - Se usan a la vez `fwg_show_tool_output` y `show_tool_output` (`utils.py:467`, `utils.py:637` e `iterator.py:571`).
  - Para el mismo concepto conviven `fwg_epw_original_lcz`, `fwg_original_lcz` (en `uhi_morph`) y `original_lcz` (en `check_lcz_availability`).
  - El prefijo `fwg_` aparece en argumentos que no son de FWG (`fwg_epw_path` y `fwg_output_dir` en `uhi_morph`).

  *Propuesta*: unificarlos, manteniendo alias obsoletos durante una versión.

- [ ] **P2 · API-08**: `uhi_morph` no devuelve la ruta del fichero generado (`utils.py:459`) e ignora `fwg_limit_variables` con v4 (`utils.py:563-573`).

- [ ] **P2 · API-09**: tipos más expresivos.
  *Propuesta*: `Literal[...]` o `Enum` para las opciones (`output_type` y los métodos del Engine), `os.PathLike` y `Sequence[str]`. Añadir el marcador `py.typed`.

- [ ] **P3 · API-10**: avisar de las opciones obsoletas también con `warnings.warn(..., DeprecationWarning)`, además del log. Por ejemplo, `fwg_diffuse_irradiation_model` y `fwg_solar_hour_adjustment` con el Engine.

- [ ] **P3 · API-11**: aceptar carpetas o patrones glob en `epw_paths`.

- [ ] **P3 · API-12**: validar la estructura del EPW antes de lanzar Java: 8 líneas de cabecera, 8.760 u 8.784 registros y campos numéricos.

- [ ] **P3 · API-13**: definir `__all__` y exportar también las constantes `ENGINE_*` y `FWG_CLI_*`.

- [ ] **P3 · API-14**: una CLI propia: `python -m pyfwg`, o `pyfwg run config.yaml` / `config.xlsx`.

- [ ] **P3 · API-15**: opciones de la JVM (`java_options=['-Xmx8g']`) y del ejecutable (`java_path`).

## 7. Calidad de código

- [ ] **P2 · CODE-01**: eliminar unas 500 líneas de código comentado. Git ya conserva el historial.
  - `api.py:105-266`, `api.py:413-567`, `api.py:355-358` y `api.py:656-659`.
  - `utils.py:417-457`, `utils.py:612-628` y `utils.py:765-843`.
  - `workflow.py:213-233`, `workflow.py:1462-1476` y `workflow.py:1685-1699`.

- [ ] **P2 · CODE-02**: eliminar imports sin usar (detectados con pylint).
  - `api.py:6-7`: `subprocess` y `time`.
  - `utils.py:18`: `datetime`.
  - `utils.py:22-23`: `GLOBAL_SCENARIOS` y `EUROPE_SCENARIOS`.
  - `utils.py:37-42`: el fallback a `importlib_resources`, que es código muerto.

- [ ] **P3 · CODE-03**: pequeños restos.
  - f-strings sin placeholders: `workflow.py:428`, `431`, `436`, `439` y `442`, y `utils.py:572`.
  - Argumentos sin usar: `workflow.py:648` (`fwg_jar_path`) y `workflow.py:1209`, `1229` y `1278` (`original_epw_path`).
  - `except:` sin tipo en `utils.py:1036`.
  - Rama muerta `hasattr(self, 'is_config_valid')` en `workflow.py:895-898`.
  - Errata `do_multithred_computation` en `workflow.py:919` y `workflow.py:1220`.
  - El log "Step 4" de `workflow.py:1055`, cuando el docstring habla del STEP 3.
  - `formatted_params` se calcula para todos los estilos, pero solo lo usa v3.

- [ ] **P2 · CODE-04**: lógica duplicada.
  - La comprobación previa de LCZ, en `api.py:51-72` y `workflow.py:1069-1097`.
  - La detección del prefijo Java, en `utils.py:531-535` y `utils.py:881-885`.
  - Las tres funciones casi idénticas de la API (`api.py:269-837`).
  - Los tres wrappers de `configure_and_preview`.

- [ ] **P2 · CODE-05**: dividir `workflow.py`, que tiene 2.034 líneas, en módulos.
  - `mapping.py`.
  - `validation.py`.
  - `commands.py`: constructores de la CLI para cada estilo.
  - `outputs.py`: recogida y renombrado de salidas.
  - `engine.py`: metadatos del JAR, que hoy están en `utils.py`.

- [ ] **P2 · CODE-06**: usar un logger por módulo (`logging.getLogger(__name__)`) en lugar del logger raíz, en las aproximadamente 152 llamadas a `logging.info`, `logging.warning`, etc. Opcionalmente, usar el formato perezoso `%s` (pylint W1203).

- [ ] **P3 · CODE-07**: evitar estructuras mutables compartidas.
  Problema: hay atributos de clase mutables como valores por defecto (`workflow.py:205-206`), y `constants.py` exporta listas y sets. Un usuario puede modificar `pyfwg.GLOBAL_SCENARIOS` y afectar así a todos los workflows.
  *Propuesta*: usar `tuple` y `frozenset`.

- [ ] **P3 · CODE-08**: modernizar el tipado a Python 3.10+ (`list[str] | None`), pasar `mypy` y añadir un docstring a `constants.py`.

- [ ] **P3 · CODE-09**: construir el comando que se imprime con `subprocess.list2cmdline` (Windows) o `shlex.join` (POSIX), en lugar del entrecomillado manual (`workflow.py:1182` y `utils.py:596`), y sin depender del índice 4 (`workflow.py:1173-1176`).

- [ ] **P3 · CODE-10**: unificar el estilo de los comentarios.
  Problema: hay comentarios en español en ficheros en inglés (`.readthedocs.yaml` y `docs/source/conf.py:49-50`), y comentarios del tipo "CRITICAL FIX" o "BUG FIX IS HERE" (`utils.py:565`).

> **Seguridad (sin acciones pendientes)**: los subprocesos reciben una lista de argumentos (sin shell), se usa `ast.literal_eval` y no `eval`, el JSON del JAR se lee con manejo de errores y los nombres de `fwg_extra_args` se validan con una regex. No hay hallazgos relevantes.

## 8. Tests

- [ ] **P1 · TEST-01**: añadir tests de regresión para todos los BUG-xx. El [Apéndice A](#apéndice-a--reproducciones-mínimas) sirve de punto de partida.

- [ ] **P1 · TEST-02**: configurar pytest.
  Problema: `pytest` recoge `tests/SS/` (3 tests con rutas absolutas a JAR en OneDrive) y no hay ninguna configuración.
  *Propuesta*: añadir `[tool.pytest.ini_options]` con `testpaths = ["tests"]`, el marcador `integration` y `filterwarnings = ["error"]`. Sacar `tests/SS` de `tests/`, o convertirlo en tests de integración que se salten si no existe `PYFWG_TEST_JAR_DIR`.

- [ ] **P1 · TEST-03**: los tests ensucian el directorio de trabajo.
  Problema: crean `out/` (`tests/test_utils.py:85-126`, con `fwg_output_dir="out"`) y `morphing_temp_results/` (`tests/test_workflow.py:115-138`, por la carpeta temporal por defecto).
  *Verificado*: ambas carpetas existen vacías en la raíz.
  *Propuesta*: una fixture `autouse` con `monkeypatch.chdir(tmp_path)`.

- [ ] **P1 · TEST-04**: cubrir las zonas sin tests (cobertura aproximada del 84 %).
  - La comprobación de LCZ en `execute_morphing` y en la API simple.
  - Las rutas de ejecución v3 y v4 de `_execute_single_morph`.
  - El manejo de `CalledProcessError` y `FileNotFoundError`.
  - `_process_generated_files` con v3 y v4, y con los ficheros de análisis `00_…`.
  - Los fallos de detección de versión.
  - La normalización en modo patrón.

- [ ] **P2 · TEST-05**: `conftest.py:6-17` contiene rutas personales absolutas, aunque solo se usan los nombres de fichero; bastan nombres simples. La fixture `real_epws` (`conftest.py:19-27`) no se usa.

- [ ] **P2 · TEST-06**: mocks frágiles.
  Problema: varios tests parchean globalmente `os.path.exists`, `os.makedirs` y `os.listdir` (`tests/test_api.py:14-17` y `37`, y `tests/test_fwg_engine.py:467-470`), y otros parchean `logging.warning` (`tests/test_iterator.py:55` y `tests/test_fwg_engine.py:532`).
  *Propuesta*: usar ficheros reales en `tmp_path` y `caplog`.

- [ ] **P2 · TEST-07**: añadir `pytest-cov` con un umbral mínimo, por ejemplo del 85 %, para subirlo después al 90 %.

- [ ] **P2 · TEST-08**: tests de ida y vuelta con Excel real.
  - Generar la plantilla, rellenarla con listas y huecos, cargarla y generar los workflows.
  - El iterador con varios EPW por fila.
  - CORDEX con EUR-11.
  - Diferencias entre Windows y Linux (separadores y barra final).

- [ ] **P3 · TEST-09**: tests de integración opcionales con FWG real, marcados como `integration` y ejecutados en local o cada noche. Pueden usar un EPW pequeño y, con el Engine, 1 GCM, 1 escenario y 1 periodo.

- [ ] **P3 · TEST-10**: un test que fije las listas de modelos y escenarios según la web oficial (ENG-06), y otro que compruebe el contenido del wheel: que incluya los tutoriales y excluya los checkpoints.

## 9. Documentación

- [ ] **P0 · DOC-01**: hay ejemplos inválidos en el README y en el docstring del iterador.
  Ubicación: `README.md:165-176` y `pyfwg/iterator.py:41-43`.
  Problema: `runs_df.loc = {...}` lanza `AttributeError: property 'loc' of 'DataFrame' object has no setter`.
  *Verificado*.
  *Propuesta*: usar `runs_df.loc[len(runs_df)] = {...}` (comprobado que funciona con listas en pandas 3) o `pd.DataFrame([...])`.

- [ ] **P1 · DOC-02**: la referencia de la API no documenta `map_categories()` ni `execute_morphing()`.
  Problema: las clases públicas los heredan de la base privada, así que no aparecen.
  *Verificado* en el HTML generado.
  *Propuesta*: añadir `:inherited-members:` (o documentar la base) y mantener `docs/source/api/*.rst` a mano, en lugar de regenerarlos con `sphinx-apidoc --force` (`dist_build_docs.bat`).

- [ ] **P1 · DOC-03**: el CHANGELOG no está listo para la versión.
  Problema:
  - Tiene una sección `[Unreleased]`, mientras `__version__ = "0.4.0"` y el README anuncia "What's New in Version 0.4.0".
  - Los enlaces del final (`CHANGELOG.md:95-99`) no cuadran: falta `[0.4.0]`, hay un enlace `[0.1.1]` sin sección y una sección `[0.1.0]` sin enlace.
  - La entrada "Parameter Precedence" (`CHANGELOG.md:23`) es incorrecta (BUG-01).

  *Propuesta*: crear `[0.4.0] - <fecha>` al publicar, corregir los enlaces y la entrada.

- [ ] **P1 · DOC-04**: documentar los requisitos de Java (17 o superior para el FWG Engine, según la documentación oficial, y la versión mínima para v3 y v4). Añadir una matriz de compatibilidad entre versiones de pyfwg y distribuciones y versiones de FWG.

- [ ] **P2 · DOC-05**: la página `pyfwg.tutorials` está vacía (`docs/source/api/pyfwg.tutorials.rst`) y conviene quitarla de la API. Corregir también el aviso de Sphinx por la doble descripción de `MorphingWorkflowCordex.cordex_domain`, documentado en el docstring y por autodoc.

- [ ] **P2 · DOC-06**: páginas nuevas.
  - Una guía de parámetros, con una tabla generada desde `get_fwg_parameters_info`.
  - Resolución de problemas: Java no encontrado, minuto 60, LCZ no disponibles y timeouts.
  - Una guía de migración de 0.3 a 0.4.
  - El CHANGELOG dentro de la documentación.
  - El diagrama de flujo: `docs/source/_static/flowchart_v0.1.0.png` existe pero no se usa en ninguna parte.

- [ ] **P2 · DOC-07**: actualizar `.readthedocs.yaml`.
  - Python 3.9 (sin soporte desde octubre de 2025) a 3.12 o 3.13.
  - `ubuntu-22.04` a `ubuntu-24.04`.
  - Añadir `sphinx: fail_on_warning: true`.
  - Comentarios en inglés.

- [ ] **P2 · DOC-08**: actualizar `docs/source/conf.py`.
  - El copyright "2025" a "2025–2026", o calcularlo.
  - Añadir `intersphinx` para Python y pandas.
  - Quitar `autosummary` si no se usa.
  - Añadir `**.ipynb_checkpoints` a `exclude_patterns` de forma explícita.

- [ ] **P2 · DOC-09**: mejorar el README.
  - Los ejemplos principales usan v3 (`README.md:57`, `136` y `159`); conviene dar prioridad a v5.
  - Falta una línea en blanco antes de `## Installation` (`README.md:40-41`).
  - Añadir una sección de citación con el DOI, y badges de CI y de cobertura.
  - Explicar qué ficheros se conservan y cómo guardar la procedencia del Engine (ENG-02).

- [ ] **P3 · DOC-10**: corregir los docstrings.
  - El atributo `epw_categories` dice "absolute path", y no es así (ROB-09).
  - La numeración de los pasos (CODE-03).
  - `fwg_jar_path` describe los nombres de JAR antiguos (`api.py:322` y `workflow.py:1535`).
  - Documentar el formato de las claves de `fwg_params`: sin el prefijo `fwg_`, y con `gcms` o `rcm_pairs` para los modelos.

- [ ] **P3 · DOC-11**: agradecimientos. La web oficial atribuye ahora el desarrollo de FWG al CURA Lab (Universidad de Coimbra). Valorar mencionarlo y citar los artículos de FWG.

## 10. Notebooks y tutoriales

- [ ] **P0 · NB-01**: rutas personales en los notebooks que se distribuyen en el wheel y en la documentación pública.
  Problema: aparecen en el código (`C:\Users\sanga\Downloads\FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar` y `D:\OneDrive - Universidad de Cádiz (uca.es)\Programas\…`) y en las salidas (entre 26 y 35 rutas temporales por notebook, con el usuario de Windows).
  *Propuesta*: una única celda de configuración (`FWG_JAR_DIR = os.environ.get("FWG_JAR_DIR", "path/to/jars")`) y limpiar o sanear las salidas.

- [ ] **P1 · NB-02**: una sola fuente para los notebooks.
  Problema: los 3 notebooks están duplicados byte a byte en `pyfwg/tutorials/` y `docs/source/tutorials/`, y hay versiones antiguas en `previous_files/`.
  *Propuesta*: que la documentación los tome del paquete, con `nbsphinx-link` o con una copia desde `conf.py`.

- [ ] **P2 · NB-03**: los contadores de ejecución de los 3 notebooks no son correlativos, señal de que se ejecutaron en desorden. Hacer "Restart & Run All" antes de publicar.

- [ ] **P2 · NB-04**: hay 23 ficheros `.ipynb_checkpoints` versionados, en `pyfwg/tutorials/` y en `docs/source/tutorials/`. Quitarlos del repositorio y añadirlos al `.gitignore`.

- [ ] **P2 · NB-05**: el wheel distribuye salidas de los tutoriales (`pyfwg/tutorials/my_parametric_study_modified.xlsx`), y quedan restos locales (`pyfwg/tutorials/morphing_temp_results*`) que `copy_tutorials` copia en las instalaciones editables.

- [ ] **P3 · NB-06**: considerar `nbstripout` (en pre-commit) o un flujo que guarde las salidas solo en la documentación.

## 11. Packaging

- [ ] **P0 · PKG-01**: falta `openpyxl`.
  Problema: `export_template_to_excel` y `load_runs_from_excel`, que son API pública, fallan tras un `pip install pyfwg` en un entorno limpio, porque pandas trata `openpyxl` como dependencia opcional.
  *Propuesta*: añadirlo a `install_requires`, o a un extra `[excel]` con un mensaje claro cuando falte.

- [ ] **P1 · PKG-02**: migrar a `pyproject.toml` (PEP 621), con metadatos, dependencias, extras, secciones `[tool.*]` (pytest, ruff, mypy y coverage) y una única fuente para la versión. Así `setup.py` y gran parte de `MANIFEST.in` dejan de hacer falta.

- [ ] **P1 · PKG-03**: corregir las versiones de Python.
  Problema: `python_requires=">=3.9"`, pero los clasificadores incluyen 3.8 y omiten 3.12, 3.13 y 3.14 (los tests pasan en 3.14). Python 3.9 no tiene soporte desde octubre de 2025.
  *Propuesta*: exigir `>=3.10` y eliminar el marcador muerto `importlib_resources; python_version<"3.9"` (`setup.py:90`).

- [ ] **P2 · PKG-04**: `colorlog` es una dependencia obligatoria, pero el código la trata como opcional. Pasarla a un extra `[color]`, o quitarla al resolver BUG-08. Fijar versiones mínimas, por ejemplo `pandas>=…` (probado con pandas 3.0.5).

- [ ] **P2 · PKG-05**: añadir extras `test`, `dev` y `docs` con versiones mínimas. `requirements-dev.txt` no incluye pytest, openpyxl ni linters, y contiene `roman`, que no parece usarse.

- [ ] **P2 · PKG-06**: limpiar `MANIFEST.in`.
  Problema: el patrón `*.py` en `pyfwg/tutorials` no encuentra nada y genera un aviso en cada build, y `prune pyfwg/wip` está obsoleto.
  *Propuesta*: corregirlo, y valorar incluir `tests/` en el sdist, que es útil para conda-forge y otros empaquetadores.

- [ ] **P3 · PKG-07**: EPW duplicados en el wheel.
  Problema: el wheel ocupa unos 1,1 MB comprimido y unos 6,4 MB instalado, e incluye 4 EPW de unos 1,5 MB, pero solo 2 son distintos: `london_uhi-type-2.epw` es igual que `GBR_London…_uhi_type-2.epw`, y `sevilla_uhi-type-1.epw` es igual que `sevilla_in_this_one…type-1.epw` (mismo MD5).
  *Propuesta*: distribuir solo los únicos y crear las copias renombradas en `copy_tutorials`.

- [ ] **P3 · PKG-08**: añadir `py.typed` y más `project_urls` (Changelog, Source y DOI), y abrir los ficheros con `encoding="utf-8"` en `setup.py:18`.

- [ ] **P3 · PKG-09**: los scripts de publicación `.bat` solo funcionan en Windows y dependen de `.pypirc`. Sustituirlos por GitHub Actions con Trusted Publishing (CI-02).

## 12. CI/CD y herramientas

- [ ] **P1 · CI-01**: no hay integración continua: no existe `.github/`.
  *Propuesta*: un workflow con una matriz de ubuntu, windows y macos, Python 3.10 a 3.14 y pandas 2.x y 3.x. Debe ejecutar los tests con cobertura, `ruff`, `mypy`, el build con `twine check` y la documentación con `-W`.

- [ ] **P2 · CI-02**: publicar en PyPI al crear un tag, con Trusted Publishing y sin tokens locales, y generar automáticamente la GitHub Release a partir del CHANGELOG.

- [ ] **P2 · CI-03**: configurar `pre-commit`.
  - ruff, para lint y formato.
  - `nbstripout`.
  - `check-added-large-files`, que habría evitado el commit de 1,2 GB de `temp_europe/`.
  - `end-of-file-fixer` y `check-merge-conflict`.

- [ ] **P3 · CI-04**: Dependabot para las actions y las dependencias. Tareas multiplataforma con `nox`, `tox` o un `Makefile` en lugar de los `.bat`.

## 13. Higiene del repositorio

- [ ] **P0 · REPO-01 (inmediato)**: hay un fichero sin seguimiento de **2,38 GB** en la raíz: `Sin confirmar 573413.crdownload`, una descarga incompleta del navegador. Un `git add -A` lo subiría. Moverlo o borrarlo, y añadir `*.crdownload` y `*.part` al `.gitignore`.

- [ ] **P1 · REPO-02**: `.git` ocupa 502 MB, con 1.335 objetos sueltos y ningún pack. Ejecutar `git gc --prune=now`, que es local y no tiene riesgo.

- [ ] **P1 · REPO-03 (decisión)**: el historial publicado en `origin/main` está inflado.
  Problema:
  - `temp_europe/`: 131 blobs y unos 1,24 GB sin comprimir de CSV con datos climáticos extraídos por FWG. Se añadió en el commit `22915c5` ("testing v4") y se borró en `1c0fb86`.
  - `backup_results/` (14,5 MB), `test_results_v3_global/` (12 MB) y `test_results_europe/` (9 MB).

  Cada clon descarga todo ese peso.
  *Opción*: `git filter-repo --invert-paths --path temp_europe/ --path backup_results/ …`, seguido de un force-push y de recrear los tags v0.1.0 a v0.3.0. Esto reescribe historia pública: cambian los SHA y hay que avisar a los colaboradores. Las versiones archivadas en Zenodo no se ven afectadas. Conviene confirmar también si esos datos se pueden redistribuir.

- [ ] **P1 · REPO-04**: hay material muerto versionado.
  - `SS/`: `pyfwg_v00` a `v18`, y notebooks y EPW antiguos.
  - `previous_files/`: wheels y sdists antiguos (unos 8 MB, que ya están en PyPI) y tutoriales antiguos.
  - `tests/SS/`: scripts con espacios en el nombre y rutas absolutas.
  - 5 Excel en la raíz (`my_parametric_study*.xlsx`).
  - `epws/`: duplicados de los EPW de los tutoriales, incluido `epws/backup/`.
  - `__init__.py` espurios en `docs/source/tutorials/` y en `docs/source/tutorials/epws/*/`.

- [ ] **P2 · REPO-05**: hay 16 copias versionadas de solo 2 EPW distintos (10 de Sevilla y 6 de Londres).

- [ ] **P2 · REPO-06**: `.idea/` está en el `.gitignore` pero sigue versionado. Ejecutar `git rm -r --cached .idea`.

- [ ] **P2 · REPO-07**: completar el `.gitignore`.
  - `*.crdownload`.
  - `*.jar`, para no subir JAR de FWG.
  - `morphing_temp_results*/`, `morphed_epws*/` y `out/`.
  - `docs/build/` y `.ipynb_checkpoints/`.
  - `runs_template.xlsx` y `pyfwg/tutorials/morphing_temp_results*/`.

  Borrar también las carpetas vacías `out/` y `morphing_temp_results/` de la raíz, que crean los tests.

- [ ] **P3 · REPO-08**: añadir un `.gitattributes` que normalice los finales de línea, trate `*.epw` como texto sin diff (o como binario) y dé un diff legible para `*.ipynb`.

- [ ] **P3 · REPO-09**: la rama remota `origin/feature/fwg-v4` ya está fusionada en `main`. Borrarla.

- [ ] **P3 · REPO-10**: hay un enlace simbólico `onedrive_backup` dentro del repositorio (ignorado por git). Sin `testpaths`, un `pytest` lanzado desde la raíz podría recorrerlo. Se resuelve con TEST-02, o sacándolo del repositorio.

## 14. Licencia y comunidad

- [ ] **P0 · LIC-01**: decidir y unificar la licencia.
  Problema: `LICENSE` es GPLv3, pero `setup.py:58` declara `MIT` y el wheel publica `License: MIT`. En el README, el badge (`README.md:4`) dice MIT y el texto (`README.md:251`) dice GPLv3.
  *Propuesta*: elegir una, y actualizar metadatos, badge y clasificador, con una expresión SPDX. Si se mantiene GPL, aclarar si es `GPL-3.0-only` o `GPL-3.0-or-later`. Cambiar de licencia requiere el acuerdo de los contribuidores.

- [ ] **P2 · LIC-02**: añadir `CITATION.cff` con el DOI de Zenodo (10.5281/zenodo.16908690), para activar el botón "Cite this repository" de GitHub. Incluir también la cita recomendada de FWG.

- [ ] **P3 · LIC-03**: añadir `CONTRIBUTING.md` (entorno, tests y estilo de commits), plantillas para issues y PR, y un `CODE_OF_CONDUCT.md`.

## 15. Roadmap de funcionalidades

Ya recogidas en otras secciones: salidas por modelo (API-04), ejecución en paralelo (PERF-02), reanudación (PERF-04), conservación de la procedencia (ENG-02), CLI propia (API-14), FWG Portugal (ENG-05) y backend Java (ENG-08).

- [ ] **P3 · FEAT-01**: una barra de progreso opcional (`tqdm`) con tiempo restante estimado para lotes largos.
- [ ] **P3 · FEAT-02**: un informe resumen del lote en CSV o HTML, con ficheros, parámetros, versiones de FWG y Java, tiempos y fallos, útil para reproducibilidad y artículos.
- [ ] **P3 · FEAT-03**: utilidades de post-proceso para comparar el EPW original con los generados, por ejemplo las medias mensuales de temperatura y radiación.

---

## Apéndice A — Reproducciones mínimas

Para todas las reproducciones basta con un EPW ficticio (`open("sevilla_2010.epw", "w").write("x")`) y el siguiente helper. Ninguna necesita Java.

```python
import pandas as pd
from pyfwg import MorphingWorkflowGlobal, MorphingWorkflowCordex, MorphingIterator

def wf(**kw):
    w = MorphingWorkflowGlobal()
    w.map_categories(["sevilla_2010.epw"], keyword_mapping={"city": {"Seville": "sevilla"}})
    w.configure_and_preview(final_output_dir="out", output_filename_pattern="{city}_{ssp}_{year}",
                            fwg_jar_path="FWG_v4.jar", **kw)
    return w
```

```python
# BUG-01: fwg_params ignored
wf(fwg_version=4, fwg_params={"winter_sd_shift": 1.5}).inputs["fwg_params"]["winter_sd_shift"]   # -> 0.0

# BUG-02: floats reach the CLI
cmd = wf(fwg_version=4, fwg_epw_original_lcz=14.0, fwg_month_transition_hours=72.0)._build_command_new_cli("a", "t.epw", "o")
[a for a in cmd if a.startswith(("-uhi", "-smooth"))]   # -> ['-smooth_hours=72.0', '-uhi=true:14.0:1']

# BUG-03: inconsistent booleans
[a for a in wf(fwg_version=4, fwg_add_uhi=1)._build_command_new_cli("a", "t.epw", "o") if a.startswith("-uhi")]  # -> ['-uhi=false']
wf(fwg_version=3, fwg_add_uhi="False").inputs["fwg_params_formatted"]["uhi_combined"]                           # -> '1:14:1'

# BUG-04: Latin-1 header corrupted
from pyfwg import sanitize_epw_minutes
open("latin.epw", "wb").write("LOCATION,M\xe1laga\n".encode("latin-1") + b"1985,1,1,1,60,A\n")
sanitize_epw_minutes("latin.epw"); open("latin.epw", "rb").readline()   # -> b'LOCATION,Mlaga\n'

# BUG-05: false overwrite with different output folders
it = MorphingIterator(MorphingWorkflowGlobal)
it.set_default_values(fwg_jar_path="FWG_v4.jar", fwg_version=4, output_filename_pattern="{city}_{ssp}_{year}", fwg_add_uhi=False)
it.generate_morphing_workflows(pd.DataFrame({"epw_paths": ["sevilla_2010.epw"] * 2, "final_output_dir": ["out_a", "out_b"]}),
                               keyword_mapping={"city": {"Seville": "sevilla"}})   # -> ValueError: Definitive file overwrite(s)...

# BUG-06: real collision missed (only the first row's pattern is checked)
it = MorphingIterator(MorphingWorkflowGlobal)
it.set_default_values(fwg_jar_path="FWG_v4.jar", fwg_version=4, final_output_dir="out", fwg_add_uhi=False)
it.generate_morphing_workflows(pd.DataFrame({
    "epw_paths": ["sevilla_2010.epw"] * 3, "fwg_gcms": [["CanESM5"], ["MIROC6"], ["MRI_ESM2_0"]],
    "output_filename_pattern": ["{city}_{ssp}_{year}_{fwg_gcms}", "{city}_{ssp}_{year}", "{city}_{ssp}_{year}"]}),
    keyword_mapping={"city": {"Seville": "sevilla"}})   # no error, but rows 2 and 3 write the same files

# BUG-07: list values + custom default
it = MorphingIterator(MorphingWorkflowGlobal); it.set_default_values(fwg_gcms=["CanESM5", "MIROC6"])
it._apply_defaults(pd.DataFrame({"epw_paths": ["a.epw", "b.epw"], "fwg_gcms": [["CanESM5", "MIROC6"], None]}))  # -> ValueError

# BUG-08: application root handlers are removed on import (run in a fresh interpreter)
import logging; logging.getLogger().addHandler(logging.StreamHandler()); import pyfwg
logging.getLogger().handlers   # -> only pyfwg's handler

# BUG-09: raise_on_error=False still raises
import subprocess; from unittest.mock import patch; from pyfwg import uhi_morph
with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "java")):
    uhi_morph(fwg_epw_path="sevilla_2010.epw", fwg_jar_path="FWG_v4.jar", fwg_output_dir="uhi",
              fwg_original_lcz=14, fwg_target_lcz=1, fwg_version=4, raise_on_error=False)   # -> CalledProcessError

# BUG-10: CORDEX + Europe v2 JAR accepted with the FWG Engine command line
w = MorphingWorkflowCordex(); w.map_categories(["sevilla_2010.epw"], input_filename_pattern=r"(?P<city>.*)")
w.configure_and_preview(final_output_dir="o", output_filename_pattern="{city}_{rcp}_{year}",
                        fwg_jar_path="FutureWeatherGenerator_Europe_v2.0.2.jar")
w.is_config_valid, w.cli_style   # -> (True, 'engine')

# DOC-01: README/docstring example
runs_df = MorphingIterator(MorphingWorkflowGlobal).get_template_dataframe()
runs_df.loc = {"epw_paths": "a.epw"}            # -> AttributeError
runs_df.loc[len(runs_df)] = {"epw_paths": "a.epw", "fwg_gcms": ["CanESM5", "MIROC6"]}   # correct form
```
