.. pyfwg documentation master file, created by
   sphinx-quickstart on Thu Aug 15 10:00:00 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pyfwg's documentation! (Version |release|)
=======================================================

`pyfwg` is a robust Python workflow manager for the Future Weather Generator command-line tools.

This documentation provides detailed information on the library's three main interfaces, designed to cater to different levels of complexity:

*   **High-Level Functions** (``morph_epw_global``, ``morph_epw_europe``): For simple, one-shot morphing tasks where you need direct control over the tool's parameters without complex file renaming.
*   **Advanced Workflow Classes** (``MorphingWorkflowGlobal``, ``MorphingWorkflowEurope``): For complex projects requiring custom file renaming based on filename parsing, and full, step-by-step control over the validation and execution process.
*   **Parametric Iterator** (``MorphingIterator``): The most powerful feature, designed for automating large batches of morphing workflows defined in a Pandas DataFrame or an Excel file, making parametric analysis simple and structured.

What's New in Version 0.3.0?
----------------------------

Version 0.3.0 introduces full support for the **Future Weather Generator v4.x** (Global) and **v2.x** (Europe), while maintaining complete backward compatibility with legacy versions.

*   **Support for FWG v4.x & Europe v2.x**: Seamlessly work with the latest versions of the tool, which use a new dynamic key-value argument system.
*   **Automatic Version Detection**: `pyfwg` automatically detects the tool version from your JAR filename (e.g., ``FutureWeatherGenerator_v4.0.2.jar``).
*   **New Utility Functions**: Includes helpers like ``get_fwg_parameters_info`` to guide you through available model arguments, and ``check_lcz_availability`` to prevent errors before execution.
*   **Enhanced Compatibility**: Improved handling of Spanish (``SPAIN_MET``) and Portuguese (``PORTUGAL_CSV``) output formats.

Requirements
------------

Before using `pyfwg`, you need to have the following installed and configured:

* **Python 3.9+**
* **Java**: The ``java`` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
* **Future Weather Generator**: You must download the appropriate ``.jar`` file from the `official website <https://future-weather-generator.adai.pt/>`_.
    * The **Global Tool** (``FutureWeatherGenerator_vX.X.X.jar``) has been tested with versions **v3.0.0**, **v3.0.1**, and **v4.0.2**.
    * The **Europe Tool** (``FutureWeatherGenerator_Europe_vX.X.X.jar``) has been tested with versions **v1.0.1** and **v2.0.2**.

Acknowledgements
----------------

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the `Future Weather Generator tool <https://future-weather-generator.adai.pt/>`_. `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   tutorials/epw_morph_global_europe_example
   tutorials/morphingworkflow_global_europe_example
   tutorials/morphingiterator_example

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
