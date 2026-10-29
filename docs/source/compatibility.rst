Supported distributions, interfaces and Excel
======================================================================

The workflow class must match the distribution. Supporting several JAR
families does not mean that every JAR can be passed to every class.

.. list-table:: Supported interface families
   :header-rows: 1
   :widths: 25 25 25 25

   * - Distribution
     - Direct API
     - Workflow class
     - Iterator input
   * - Global 5.2.0 (FWG Engine)
     - ``morph_epw_global``
     - ``MorphingWorkflowGlobal``
     - DataFrame or XLSX with the Global class
   * - Europe EUR-11 3.2.0
     - ``morph_epw_europe`` or ``morph_epw_cordex``
     - ``MorphingWorkflowEurope`` or ``MorphingWorkflowCordex``
     - DataFrame or XLSX with either compatible class
   * - Other eight CORDEX-CMIP5 regions 1.2.0
     - ``morph_epw_cordex``
     - ``MorphingWorkflowCordex``
     - DataFrame or XLSX with the Cordex class

``MorphingIterator`` receives a workflow class, for example
``MorphingIterator(MorphingWorkflowCordex)``. One Cordex iterator can contain
different regional JARs, including EUR-11 v3+, in different rows. A Global JAR
cannot be included in that Cordex batch; create a Global iterator for it.
Incompatible JAR/class combinations are rejected during configuration.

Verified execution matrix (2026-10-29)
------------------------------------------------------------

.. list-table:: Real weather generation through every interface
   :header-rows: 1
   :widths: 32 17 17 17 17

   * - JAR / version
     - Direct API
     - Workflow
     - DataFrame iterator
     - XLSX iterator
   * - Global 5.2.0
     - Passed
     - Passed
     - Passed
     - Passed
   * - Europe EUR-11 3.2.0
     - Passed
     - Passed
     - Passed
     - Passed
   * - AFR-22, AUS-22, CAM-44, MNA-22, NAM-44, SAM-44, SEA-22, WAS-22 (each 1.2.0)
     - All eight passed
     - All eight passed
     - All eight passed
     - All eight passed

These are 40 individual generations. Two additional nine-row regional XLSX
batches passed: one with a single model per row, and one with each region's
complete eligible ensemble (29 members in total). All 58 generations produced
an EPW/STAT pair, with 8,760 hourly records, preserved station coordinates and
changed temperature values. The Europe row uses the Europe interfaces; EUR-11
also passed the Cordex API/workflow checks and both mixed-region Excel batches.

Thirty JAR/class combinations additionally checked acceptance of matching
classes and rejection of incompatible classes. Nine regional catalog checks
and nine Java CLI startup checks passed. After moving the regional JARs to an
external drive with spaces in its path, these 48 checks and the nine-row
single-model XLSX batch passed again.

The first single-model mixed batch lacked SEA-22 and WAS-22 outputs; its
retained startup log does not establish a cause. The complete repeat passed.
The original failed attempt and successful repeat are retained separately in
the local validation evidence. No automatic retry was added to the library.

Coverage uses Windows, Python 3.14, Java 25, one real EPW per region (Global
uses Seville), one available scenario, 2050, IDW, MINIMAL output and one
computation/I/O thread. Global uses CanESM5; a full Global ensemble was not
tested. This matrix does not cover every scientific option, scenario, period,
baseline or Java version. See :doc:`cordex` for baseline/reference-period
limitations. The local checkout retains detailed artifacts under
``build/interface-validation``; they are not packaged with the library.

Using a real Excel workbook
---------------------------

Use the library's export and load functions so list and dictionary cells reach
the iterator as Python objects:

.. code-block:: python

   from pyfwg import (
       MorphingIterator, MorphingWorkflowCordex,
       export_template_to_excel, load_runs_from_excel,
   )

   iterator = MorphingIterator(MorphingWorkflowCordex)
   iterator.set_default_values(output_filename_pattern="{region}_{rcp}_{year}")
   export_template_to_excel(iterator, "cordex-runs.xlsx")
   # Fill one row per run in Excel, then save the workbook.
   runs = load_runs_from_excel("cordex-runs.xlsx")
   iterator.generate_morphing_workflows(runs)
   # Inspect the plan and the configuration warnings before generation.
   iterator.run_morphing_workflows()

Export to a new filename: ``export_template_to_excel`` replaces an existing
workbook at the supplied path. Load edited files with ``load_runs_from_excel``
rather than passing an unconverted ``pandas.read_excel`` result.

The notebook examples include a populated workbook in addition to a blank
template. Typical cell contents are:

.. list-table:: Excel cell examples for a regional run
   :header-rows: 1
   :widths: 30 70

   * - Column
     - Cell contents
   * - ``epw_paths``
     - ``['C:/weather/NAM-44.epw']`` (or a single path as plain text)
   * - ``fwg_jar_path``
     - Full path to the JAR for this row's region
   * - ``fwg_rcm_pairs``
     - ``['CCCma-CanESM2-SMHI-RCA4']``
   * - ``fwg_scenarios``
     - ``['rcp45']``
   * - ``fwg_timeframes``
     - ``[2050]``
   * - ``keyword_mapping``
     - ``{'region': {'NAM-44': 'NAM-44'}}``
   * - ``fwg_extra_args``
     - ``{'threads': 1, 'io_threads': 1}``
   * - ``fwg_params``
     - ``{'month_transition_hours': 48, 'create_ensemble': False}``
   * - ``fwg_month_transition_hours``
     - Numeric ``24`` overrides the ``48`` in this row's ``fwg_params``
   * - ``fwg_create_ensemble``
     - Boolean ``TRUE``/``FALSE``, numeric ``1``/``0``, or text ``true``/``false``

Leave a cell empty to use an iterator default, or, when no iterator default is
set, the value in ``fwg_params`` or the workflow's own default. Use Python
list/dictionary notation for structured cells; do not enter executable code.
Scenario choices must match each row's JAR. Output directories and filename
categories must distinguish runs to prevent overwrites.

Support policy
--------------

Supported and verified binaries are Global 5.2.0, Europe EUR-11 3.2.0 and
the other eight CORDEX-CMIP5 distributions 1.2.0 (FWG Engine 1.1.0).
Older Global v3/v4 and Europe v1/v2 releases are outside the supported scope.
Their original binaries were unavailable for this validation, so no current
compatibility guarantee is made. Historical CLI adapters and their unit tests
remain in the source; they do not establish supported binary compatibility.
The tutorials and real-JAR integration suite target Engine distributions.

The supported Engine distributions do not implement UHI/LCZ morphing.
Other Engine versions require their own real-JAR validation; automatic
metadata detection alone does not certify a release.

Repeatable interface checks
---------------------------

The optional ``tests/test_fwg_interfaces_integration.py`` suite checks the
public API, workflow, DataFrame iterator and the complete Excel path:
export a template, populate real worksheet cells, save, load through pyfwg,
prepare the iterator, execute Java and inspect the final EPW/STAT pairs.
It also runs two mixed-region XLSX batches (single-model and full eligible
ensemble) and checks every installed JAR against
all three workflow classes, including rejection of incompatible combinations.

.. code-block:: text

   python -m pytest tests/test_fwg_interfaces_integration.py --fwg-jar-dir "path/to/regional-jars" --fwg-extra-jar-dir "path/to/global-jar-folder" --fwg-epw-dir "path/to/regional-epws" --fwg-cache-dir "path/on/a/drive/with/space" --fwg-java "path/to/java" -v -rs

``--fwg-extra-jar-dir`` is repeatable and useful when Global is stored in a
different folder. For these tests, Global uses ``EUR-11.epw`` as the baseline;
regional JARs use ``<domain>.epw``. Each per-interface case selects one model,
scenario and period. The ensemble XLSX case selects every eligible member
unless ``--fwg-ensemble-size`` explicitly limits it. Unit tests and
configuration-only checks do not establish successful weather generation.

To check class compatibility without starting Java, add ``-m "not morphing"``.
To run only the generation cases, add ``-m morphing``. The tests preserve
outputs, populated workbooks and diagnostics in pytest's temporary directory;
use a dedicated ``--basetemp`` to choose its location. Pytest clears that
directory on a subsequent run. Keep climate caches on a drive with sufficient
space, and remove only the dedicated test caches after completion.
