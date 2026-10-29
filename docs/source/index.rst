.. pyfwg documentation master file, created by
   sphinx-quickstart on Thu Aug 15 10:00:00 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pyfwg's documentation! (Version |release|)
=======================================================

`pyfwg` is a robust Python workflow manager for the Future Weather Generator command-line tools.

This documentation provides detailed information on the library's three main interfaces, designed to cater to different levels of complexity:

*   **High-Level Functions** (``morph_epw_global``, ``morph_epw_europe``, ``morph_epw_cordex``): For simple, one-shot morphing tasks where you need direct control over the tool's parameters without complex file renaming.
*   **Advanced Workflow Classes** (``MorphingWorkflowGlobal``, ``MorphingWorkflowEurope``, ``MorphingWorkflowCordex``): For complex projects requiring custom file renaming based on filename parsing, and full, step-by-step control over the validation and execution process.
*   **Parametric Iterator** (``MorphingIterator``): The most powerful feature, designed for automating large batches of morphing workflows defined in a Pandas DataFrame or an Excel file, making parametric analysis simple and structured.

What's New in Version 0.4.0?
----------------------------

Version 0.4.0 adds support for the **FWG Engine**, the shared engine of the latest Future Weather Generator distributions: **Global v5.x**, **Europe v3.x** and the new **CORDEX regional** distributions. Supported binaries are Global 5.2.0, Europe EUR-11 3.2.0 and the eight other regional distributions 1.2.0. Older Global/Europe releases are outside the supported scope; see :doc:`compatibility`.

*   **Global v5.x and Europe v3.x**: Use them with the same classes and functions as before. `pyfwg` detects the version from the JAR and builds the new command line for you.
*   **CORDEX Regional Distributions**: ``MorphingWorkflowCordex`` and ``morph_epw_cordex`` accept all nine CORDEX-CMIP5 domains, including Europe EUR-11 v3+. The installed manifest determines the models, scenarios, periods and grid topology. See :doc:`cordex` and the :doc:`regional notebook <tutorials/cordex_regions_example>`.
*   **New FWG Engine Options**: Select scenarios and future periods (``fwg_scenarios``, ``fwg_timeframes``), solar decomposition, illuminance and infrared models, uncertainty cases (``fwg_uncertainty_variant``), output profile and a shared climate-data cache (``fwg_model_unzipped_folder``). Any other option of the tool can be passed with ``fwg_extra_args``.
*   **JAR Inspection**: ``get_fwg_distribution_info`` reads the scenarios, periods and climate models packaged in FWG Engine JARs, which `pyfwg` also uses to validate your configuration.
*   **Urban Heat Island**: The supported FWG Engine distributions do not implement UHI or LCZ morphing.

Requirements
------------

Before using `pyfwg`, you need to have the following installed and configured:

* **Python 3.9+**
* **Java**: The ``java`` command must be accessible from your system's terminal (i.e., it must be in your system's PATH). FWG Engine distributions require Java 17+; the regional generation checks below used Java 25.
* **Future Weather Generator**: You must download the appropriate ``.jar`` file from the `official website <https://future-weather-generator.adai.pt/>`_.
    * The **FWG Engine distributions** have been tested with **Global v5.2.0**, **Europe EUR-11 v3.2.0** and the eight other **CORDEX-CMIP5 regional distributions v1.2.0**, using FWG Engine v1.1.0. On 2026-10-28, all nine regional JARs passed real generation with a single model and the full eligible ensemble, for one scenario and the 2050 period per region. See :doc:`cordex` for the validation matrix and limits of that coverage.

Choose a tutorial
-----------------

Start with :doc:`tutorials/cordex_regions_example` to select a regional JAR,
inspect its catalog, and use the direct API, workflow or iterator. Its initial
configuration leaves generation disabled so you can review the regional plans
before extracting climate data.

Both versions of every tutorial include saved execution outputs, tables and
embedded climate-comparison plots. Read the Docs renders these outputs without
running Java. The full notebooks retain configuration helpers and checks;
the ``*_simple`` copies use explicit paths and direct calls without fallback
branches. They coexist so you can compare their style.

The full notebooks generate weather when ``FWG_RUN_MORPHING=1`` or
``RUN_MORPHING=True``. The simplified notebooks run generation directly when
their cells are executed. Viewing the published pages does not execute either
version. Download a notebook from its page, or copy the tutorials from an
installed package:

.. code-block:: python

   from pyfwg import copy_tutorials
   copy_tutorials("./pyfwg_tutorials")

Install the plotting and notebook dependencies with ``pip install pyfwg[tutorials]``.
See :doc:`tutorial_comparison` for the side-by-side choice of examples.

JARs and public regional EPWs are separate downloads. The regional notebook
links to the public samples used in testing and explains the cache and
diagnostic folders.

Acknowledgements
----------------

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the `Future Weather Generator tool <https://future-weather-generator.adai.pt/>`_. `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   cordex
   compatibility
   tutorial_comparison
   tutorials/cordex_regions_example
   tutorials/epw_morph_global_europe_example
   tutorials/morphingworkflow_global_europe_example
   tutorials/morphingiterator_example

.. toctree::
   :maxdepth: 1
   :caption: Simplified alternatives

   tutorials/cordex_regions_example_simple
   tutorials/epw_morph_global_europe_example_simple
   tutorials/morphingworkflow_global_europe_example_simple
   tutorials/morphingiterator_example_simple

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
