Full and simplified notebook examples
=====================================

Both alternatives contain actual Java execution outputs and embedded figures.
You can compare them here without installing FWG or running the notebooks.
The saved runs were executed on 2026-10-29 with Python 3.14 and Java 25:
eight notebooks, 46 future EPW/STAT pairs and nine embedded figures. Their
package and documentation copies preserve identical outputs.
The full versions keep catalog selection, validation and configuration helpers.
The simplified copies use explicit paths, parameters and direct calls, with no
path fallback branches or preventive ``if`` blocks. They show fewer cases so
the main steps remain visible.

.. list-table:: Choose an example
   :header-rows: 1
   :widths: 20 40 40

   * - Topic
     - Full version
     - Simplified copy
   * - Regional distributions
     - :doc:`Nine-region catalog and several interfaces <tutorials/cordex_regions_example>`
     - :doc:`One North America API call <tutorials/cordex_regions_example_simple>`
   * - Direct API
     - :doc:`Global, Europe and regional examples <tutorials/epw_morph_global_europe_example>`
     - :doc:`One Global CMIP6 call <tutorials/epw_morph_global_europe_example_simple>`
   * - Workflow
     - :doc:`Global, Europe and regional previews <tutorials/morphingworkflow_global_europe_example>`
     - :doc:`One Europe map/preview/execute sequence <tutorials/morphingworkflow_global_europe_example_simple>`
   * - Iterator and Excel
     - :doc:`Global and regional DataFrame/XLSX examples <tutorials/morphingiterator_example>`
     - :doc:`Two regional rows through Excel <tutorials/morphingiterator_example_simple>`

The graphs compare the original station EPW with generated 2050 and 2080
climates. Full versions show monthly temperature, temperature change, humidity
and mean daily global horizontal irradiation. Simplified copies focus on
temperature and its difference from the original. The periods identify FWG
climate projections, not individual forecast years. These illustrations do not
replace an assessment of the baseline period, model choice or uncertainty.

Outputs are stored in the notebooks, including PNG image data. The Sphinx
configuration uses ``nbsphinx_execute = 'never'``: Read the Docs includes the
saved results without needing Java, climate JARs or local EPWs. Downloadable
notebooks preserve the same results. Regeneration requires the listed files
and Java; reading the documentation does not.

For the simplified examples, start Jupyter from the project root, edit the
explicit paths, and run cells in order. These copies deliberately let Python
or pyfwg report missing-file and configuration errors. Running all cells starts
weather generation. The full versions retain an opt-in generation switch.
