CORDEX regional distributions
=============================

``MorphingWorkflowCordex`` and ``morph_epw_cordex`` accept the nine
CORDEX-CMIP5 regional distributions: EUR-11, MNA-22, AFR-22, NAM-44,
CAM-44, SAM-44, WAS-22, SEA-22 and AUS-22. The verified releases are
Europe EUR-11 3.2.0 and the eight other distributions 1.2.0.

See :doc:`compatibility` for the class/JAR compatibility matrix, Excel cell
formats, cross-interface tests and the supported-version policy.

Start with the :doc:`regional notebook <tutorials/cordex_regions_example>`
or :download:`download its Jupyter source <tutorials/cordex_regions_example.ipynb>`.
It covers the direct API, filename previews and a batch with different JARs
per region. The :doc:`direct API <tutorials/epw_morph_global_europe_example>`,
:doc:`workflow <tutorials/morphingworkflow_global_europe_example>` and
:doc:`iterator <tutorials/morphingiterator_example>` notebooks also include
examples for the current Global, Europe and CORDEX distributions.

Configure the notebooks
-----------------------

Each notebook has one configuration section. Set these environment variables
before starting Jupyter, use the optional ``fwg.local.json`` file in the
project/working folder, or edit the paths in that section. Environment variables
override the JSON file, which overrides the notebook defaults. The local JSON
is excluded from Git. For example::

   {
     "FWG_JAR_DIR": "F:/Python/pyfwg files",
     "FWG_GLOBAL_JAR_PATH": "C:/downloads/FutureWeatherGenerator-CMIP6-Global-v5.2.0.jar",
     "FWG_CACHE_DIR": "D:/fwg-cache",
     "FWG_OUTPUT_DIR": "D:/fwg-results"
   }

JARs may live on an external drive; keep it connected while Java runs. Spaces
in folder names are supported. Moving JARs does not move existing caches or
update the absolute paths inside previously saved Excel workbooks. Edit those
cells before reusing a workbook after a move. New notebook workbooks use the
configured paths.


.. list-table:: Notebook folders
   :header-rows: 1
   :widths: 25 75

   * - Variable
     - Meaning and default
   * - ``FWG_JAR_DIR``
     - JAR folder; defaults to the checkout root. Keep one JAR version per domain in the selected folder. Renamed JARs are identified from their manifests.
   * - ``FWG_GLOBAL_JAR_PATH``
     - Optional full path to Global 5.2.0 when stored outside the regional JAR folder.
   * - ``FWG_JAVA``
     - Optional Java executable; its directory is prepended to PATH in the notebook.
   * - ``FWG_EPW_DIR``
     - Real baselines named ``<domain>.epw``. Defaults to retained ``build/cordex-validation/epws`` samples when present, otherwise ``epws/cordex`` in the checkout.
   * - ``FWG_CACHE_DIR``
     - Shared extracted climate data; defaults to ``~/fwg_model_cache``. Regional examples separate caches by distribution ID and version.
   * - ``FWG_OUTPUT_DIR``
     - Regional results and temporary diagnostics; defaults to ``build/cordex-tutorial`` in the checkout.

Outside a checkout, the current working directory is used as the root for
these defaults. ``FWG_JAR_DIR``, ``FWG_EPW_DIR`` and ``FWG_CACHE_DIR`` also
configure the integration tests below; ``FWG_OUTPUT_DIR`` is a notebook
convention. The library itself takes explicit path arguments.

Run the configuration and regional helper cells first. ``RUN_MORPHING=False``
inspects the inputs and prepares regional previews without starting Java.
Change it to ``True`` to generate weather. This flag applies to the updated
examples, including Global and Europe. Saved outputs include actual runs enabled
with ``FWG_RUN_MORPHING=1``, tables and embedded figures. Read the Docs displays
them without executing Java. Each notebook uses its own output subfolder.
The :doc:`simplified copies <tutorial_comparison>` run their examples directly.

The executed tutorials use one model, one common scenario and the 2050/2080
periods so both future climates can be compared with the original EPW. Use
``ensemble=True`` in ``regional_inputs`` (or ``USE_ENSEMBLE=True`` in the
regional notebook) for all eligible members. The helper checks that the
selection has a common scenario and period, and that the regional EPW exists.

Inspect the installed distribution
----------------------------------

The JAR's distribution manifest and model catalog determine its region,
models, scenarios and periods, including when the JAR has been renamed.
``CORDEX_REGIONS`` provides fallback lists when metadata is unavailable.

.. code-block:: python

   from pyfwg import get_fwg_distribution_info, morph_epw_cordex

   jar = "jars/FutureWeatherGenerator-CORDEX-CMIP5-North-America-NAM-44-v1.2.0.jar"
   info = get_fwg_distribution_info(jar)
   if info is None:
       raise ValueError("The JAR is missing, unreadable, or is not an FWG Engine distribution.")
   print(info["domain"], info["scenarios"], info["timeframes"])
   for model, details in info["model_details"].items():
       print(model, details["scenarios"], details["grid_topology"])

   files = morph_epw_cordex(
       epw_paths="epws/toronto.epw",
       fwg_jar_path=jar,
       output_dir="results/NAM-44",
       fwg_rcm_pairs=[info["models"][0]],
       fwg_scenarios=["rcp85"],
       fwg_timeframes=[2050],
       fwg_interpolation_method_id="IDW",
       fwg_model_unzipped_folder="cache/fwg-cordex-cmip5-north-america-nam-44/1.2.0",
       temp_base_dir="temp/NAM-44",
       delete_temp_files=False,
   )

For custom filenames, use ``MorphingWorkflowCordex`` with the ``{rcp}``
and ``{year}`` placeholders. For a study spanning several regions, pass a
different ``fwg_jar_path`` in each row of
``MorphingIterator(MorphingWorkflowCordex)``. Include the region in a mapped
filename category or use separate output directories to prevent collisions.
Do not impose a common scenario on every region: for example, MNA-22 does
not provide RCP4.5. Each iterator row can supply its own JAR, model selection,
scenario list, EPW and cache directory. The iterator retains shared caches;
it does not free the previous region's data when the next row starts.

Regional constraints
--------------------

* Select an EPW whose location is inside the models' native domain. The
  engine validates spatial coverage; a region name is not a bounding box.
* Scenarios differ by region. MNA-22 only has RCP8.5; NAM-44 and SEA-22
  have RCP4.5/RCP8.5; AFR-22, WAS-22 and AUS-22 have RCP2.6/RCP8.5;
  EUR-11, CAM-44 and SAM-44 have all three. Consult the installed catalog
  for the authoritative values and each product's availability.
* ``BI`` (integer ID ``1``) needs a ``RECTILINEAR_GEOGRAPHIC`` grid.
  Rotated/projected regional products support ``IDW``, ``NP``, ``AVG4P``,
  ``SCI``, ``SGBI`` and ``STBI`` instead. Validation checks the topology
  of the selected products, including default ensemble members.
* The engine treats underscores and hyphens as aliases in model IDs.
  pyfwg normalizes and deduplicates them. Selecting one distinct product
  disables ensemble mode. Empty explicit selections are invalid.
* FWG Engine regional distributions do not implement UHI.

Reproducible integration checks
--------------------------------

On 2026-10-28, local generation checks passed for EUR-11 v3.2.0 and all
eight other regional JARs v1.2.0 (FWG Engine 1.1.0): 18 generation cases,
covering a single model and the complete eligible ensemble per domain,
plus 18 catalog/CLI-help checks. Each region used one real EPW, one shared
scenario and the 2050 period. The full EUR-11 ensemble included seven models.
Baselines rejected by SolarQC in New Delhi and Suvarnabhumi were replaced
with public samples from Mumbai and Singapore for the successful checks.

.. list-table:: Real generation checks, 2026-10-28
   :header-rows: 1
   :widths: 12 12 18 16 22 20

   * - Domain
     - JAR version
     - Eligible ensemble members
     - EPW station
     - Scenario / period
     - API / ensemble
   * - EUR-11
     - 3.2.0
     - 7
     - Seville
     - rcp26 / 2050
     - Passed / passed
   * - MNA-22
     - 1.2.0
     - 2
     - Cairo
     - rcp85 / 2050
     - Passed / passed
   * - AFR-22
     - 1.2.0
     - 3
     - Nairobi
     - rcp26 / 2050
     - Passed / passed
   * - NAM-44
     - 1.2.0
     - 2
     - Toronto
     - rcp45 / 2050
     - Passed / passed
   * - CAM-44
     - 1.2.0
     - 3
     - San Jose
     - rcp26 / 2050
     - Passed / passed
   * - SAM-44
     - 1.2.0
     - 5
     - Sao Paulo
     - rcp26 / 2050
     - Passed / passed
   * - WAS-22
     - 1.2.0
     - 2
     - Mumbai
     - rcp26 / 2050
     - Passed / passed
   * - SEA-22
     - 1.2.0
     - 2
     - Singapore
     - rcp45 / 2050
     - Passed / passed
   * - AUS-22
     - 1.2.0
     - 3
     - Sydney
     - rcp26 / 2050
     - Passed / passed

The regional notebook links to the eight public TMYx 2009-2023 samples from
`Climate.OneBuilding <https://climate.onebuilding.org/>`_ (Linda K. Lawrie and
Drury B. Crawley). The Europe check used the Seville IWEC already in the
repository. These baseline periods do not establish compatibility with the
models' 1976-2005 climate reference period: FWG reports reference-period
mismatches, and choosing a baseline for a study requires a separate assessment.

The later cross-interface campaign also passed the API, workflow, DataFrame
iterator and XLSX iterator for all ten available JARs, plus mixed-region
single-model and complete-ensemble XLSX batches. See :doc:`compatibility`
for the 58-generation matrix, the repeat after relocating JARs to an external
drive and the exact limits of that coverage.

Run these commands from a checkout with pytest and pyfwg's dependencies
installed. Java 17+ is needed for CLI and generation tests.

The ordinary suite uses synthetic JAR metadata and mocked weather files:

.. code-block:: text

   python -m pytest

Check local JAR catalogs without Java:

.. code-block:: text

   python -m pytest tests/test_cordex_integration.py --fwg-jar-dir "path/to/jars" -m "not java" -v -rs

Also start each JAR's CLI help:

.. code-block:: text

   python -m pytest tests/test_cordex_integration.py --fwg-jar-dir "path/to/jars" -m "not morphing" -v -rs

Use ``--fwg-java "path/to/jdk/bin/java.exe"`` to select a particular JDK.
``FWG_JAR_DIR`` and ``FWG_JAVA`` supply the same defaults. All versions
present in the folder are tested. A missing region is reported as skipped;
a matching JAR whose metadata cannot be read fails its catalog check.

Generation is opt-in. Supply real baseline files named ``<domain>.epw``
(for example, ``NAM-44.epw`` and ``MNA-22.epw``) inside a separate folder:

.. code-block:: text

   python -m pytest tests/test_cordex_integration.py --fwg-jar-dir "path/to/jars" --fwg-epw-dir "path/to/regional-epws" -m morphing -v -rs

``FWG_EPW_DIR`` can supply the baseline folder. Each available region
runs its full eligible ensemble through the workflow, followed by a single
model through the simple API, for one shared scenario and one period. Missing baselines are
skipped. These runs extract climate data and can take substantially longer
than the catalog checks. Temporary files, engine diagnostics and generated
weather remain in pytest's temporary directory for inspection; use
``--basetemp`` with a dedicated disposable directory to choose its location
(pytest clears that directory on the next run).

To reuse extracted climate data between the single-model and ensemble runs,
set ``--fwg-cache-dir "path/to/cache"`` or ``FWG_CACHE_DIR``. Each domain gets
its own cache subfolder. If disk space is limited, run one domain at a time
with ``-k NAM-44`` (for example), and remove that domain's cache after its
tests complete. Keep the baselines, logs and generated weather separately.
Choose a drive with enough free space: the EUR-11 v3.2.0 climate archives
contain about 11.3 GB of uncompressed data, in addition to the JAR and
temporary extraction overhead. ``--fwg-ensemble-size N`` optionally limits
the generation test to the first N eligible members (at least two); omit it
to test the complete ensemble.

The engine's SolarQC preprocessing can reject a baseline before any climate
model is used. Inspect ``metadata/solarqc_preprocessing_failure.txt`` in the
run's temporary directory when this happens. A rejected EPW is not evidence
that the regional JAR or pyfwg's regional command construction is unsupported.

Keep ``delete_temp_files=False`` while diagnosing a run and, if needed, set
``fwg_extra_args={"save_technical_log": True}`` for the application logs.
Per-EPW diagnostics are under ``<temp_base_dir>/<EPW stem>/``; the direct API
returns the collected future files, while a workflow uses its rename plan.
A failed Java execution is logged and can leave no final files. Always inspect
the output after generation as well as the configuration preview.

The initial NAM-44/MNA-22 tests on D: also recorded a failure preparing a
second climate product after a single-model run. Fresh-cache ensembles and
direct-engine diagnostic repetitions passed; the NAM-44 single-model-to-ensemble
sequence passed when repeated on C:. The initial cause was not established.
No silent retries or JAR modifications were used to obtain the passing runs.

After reviewing the outputs, remove only the temporary directories and specific
distribution/version caches you no longer need, when no run is using them.
``delete_temp_files=True`` removes per-EPW temporary data after successful
generation; it does not delete an explicitly configured shared climate cache.

The checks require a nonempty future EPW/STAT pair and a matching EPW record
count. They verify integration, not the scientific accuracy of climate
signals or every combination of models, scenarios and interpolation methods.
Do not use metadata/help checks as evidence of successful weather generation.
Use a valid EPW for each region, rather than relocating a European sample by
editing its coordinates.

Reference contracts
-------------------

* `FWG distributions <https://future-weather-generator.adai.pt/documentation/distributions.html>`_
* `FWG spatial interpolation <https://future-weather-generator.adai.pt/documentation/spatial-interpolation.html>`_
* `FWG CLI reference <https://future-weather-generator.adai.pt/documentation/cli-reference.html>`_
* `FWG source repository <https://bitbucket.org/cling-project/futureweathergenerator>`_
