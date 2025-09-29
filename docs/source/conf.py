# docs/source/conf.py

import os, sys, re

# -- Path setup --------------------------------------------------------------
# Add the project root to the Python path so Sphinx can find your code.
# This assumes conf.py is in docs/source, and the pyfwg package is at the root.
sys.path.insert(0, os.path.abspath('../..'))


# --- Function to dynamically read the version from __init__.py ---
def get_version():
    """
    Reads the version string from the package's __init__.py file.
    """
    # Construct the path to the __init__.py file.
    init_py_path = os.path.join(os.path.dirname(__file__), '..', '..', 'pyfwg', '__init__.py')
    with open(init_py_path, "r") as f:
        version_file = f.read()

    # Use regex to find the __version__ string.
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)

    if version_match:
        return version_match.group(1)

    raise RuntimeError("Unable to find version string.")

# The full version, including alpha/beta/rc tags, read dynamically.
release = get_version()
# The short X.Y version.
version = '.'.join(release.split('.')[:2])

# -- Project information -----------------------------------------------------
project = 'pyfwg'
copyright = '2025, Daniel Sánchez-García'
author = 'Daniel Sánchez-García'

# -- General configuration ---------------------------------------------------
# Add any Sphinx extension module names here, as strings.
extensions = [
    'sphinx.ext.autodoc',      # Core library to pull documentation from docstrings
    'sphinx.ext.napoleon',     # Support for Google and NumPy style docstrings
    'sphinx.ext.viewcode',     # Add links to highlighted source code
    'sphinx.ext.autosummary',  # Create summary tables
    'nbsphinx',
]

# (Opcional) Para controlar cuándo se ejecuta el código del notebook
# 'auto': se ejecuta si no hay salida guardada. 'always': se ejecuta siempre. 'never': nunca se ejecuta.
nbsphinx_execute = 'never'

# Autodoc settings to ensure members are documented
autodoc_member_order = 'bysource'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# The theme to use for HTML and HTML Help pages.
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']