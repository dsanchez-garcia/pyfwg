Simple and advanced tutorials
=============================

Both alternatives contain actual Java execution outputs and embedded figures.
You can compare them here without installing FWG or running the notebooks.
The saved runs were executed on 2026-10-29 with Python 3.14 and Java 25:
eight notebooks, 46 future EPW/STAT pairs and nine embedded figures. Their
package and documentation copies preserve identical outputs.
Simple tutorials use explicit paths, parameters and direct calls, with no
path fallback branches or preventive ``if`` blocks. They show fewer cases so
the main steps remain visible. Advanced tutorials keep catalog selection,
validation and configuration helpers. The navigation lists the simple
tutorials first, then the advanced tutorials in a separate section.

.. list-table:: Choose an example
   :header-rows: 1
   :widths: 20 40 40

   * - Topic
     - Simple tutorial
     - Advanced tutorial
   * - Regional distributions
     - :doc:`One North America API call <tutorials/cordex_regions_example_simple>`
     - :doc:`Nine-region catalog and several interfaces <tutorials/cordex_regions_example>`
   * - Direct API
     - :doc:`One Global CMIP6 call <tutorials/epw_morph_global_europe_example_simple>`
     - :doc:`Global, Europe and regional examples <tutorials/epw_morph_global_europe_example>`
   * - Workflow
     - :doc:`One Europe map/preview/execute sequence <tutorials/morphingworkflow_global_europe_example_simple>`
     - :doc:`Global, Europe and regional previews <tutorials/morphingworkflow_global_europe_example>`
   * - Iterator and Excel
     - :doc:`Two regional rows through Excel <tutorials/morphingiterator_example_simple>`
     - :doc:`Global and regional DataFrame/XLSX examples <tutorials/morphingiterator_example>`

The graphs compare the original station EPW with generated 2050 and 2080
climates. Advanced tutorials show monthly temperature, temperature change, humidity
and mean daily global horizontal irradiation. Simple tutorials focus on
temperature and its difference from the original. The periods identify FWG
climate projections, not individual forecast years. These illustrations do not
replace an assessment of the baseline period, model choice or uncertainty.

Outputs are stored in the notebooks, including PNG image data. The Sphinx
configuration uses ``nbsphinx_execute = 'never'``: Read the Docs includes the
saved results without needing Java, climate JARs or local EPWs. Downloadable
notebooks preserve the same results. Regeneration requires the listed files
and Java; reading the documentation does not.

For the simple tutorials, start Jupyter from the project root, edit the
explicit paths, and run cells in order. These copies deliberately let Python
or pyfwg report missing-file and configuration errors. Running all cells starts
weather generation. Advanced tutorials retain an opt-in generation switch.
