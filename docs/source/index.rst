.. pyfwg documentation master file, created by
   sphinx-quickstart on Thu Aug 15 10:00:00 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to pyfwg's documentation!
=================================

`pyfwg` is a robust, step-by-step Python workflow manager for the FutureWeatherGenerator command-line tool.

This documentation provides detailed information on the two main interfaces of the library: the simple, one-shot `morph_epw` function for direct usage, and the powerful `MorphingWorkflow` class for complex, step-by-step projects.

Requirements
------------

Before using `pyfwg`, you need to have the following installed and configured:

* **Python 3.9+**
* **Java**: The ``java`` command must be accessible from your system's terminal (i.e., it must be in your system's PATH).
* **FutureWeatherGenerator**: You must download the tool's ``.jar`` file. This library has been tested with FutureWeatherGenerator **v3.0.0** and **v3.0.1**.
    * `Download from the official website <https://future-weather-generator.adai.pt/>`_

Acknowledgements
----------------

This library would not be possible without the foundational work of **Eugénio Rodrigues (University of Coimbra)**, the creator of the `FutureWeatherGenerator tool <https://future-weather-generator.adai.pt/>`_. `pyfwg` is essentially a Python wrapper designed to automate and streamline the use of his powerful command-line application.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   tutorials/epw_morph_example
   tutorials/morphingworkflow_example

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`