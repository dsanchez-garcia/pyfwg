# setup.py

"""
This is the setup script for the pyfwg package.

It uses setuptools to handle the packaging and distribution of the library.
This script provides the necessary metadata for PyPI, defines dependencies,
and configures how the package is built.
"""

import re
from setuptools import setup, find_packages

# --- Version Handling ---
# Read the version number from the package's __init__.py file.
# This is a robust way to ensure the version is consistent without
# importing the package, which can cause dependency issues during setup.
with open("pyfwg/__init__.py", "r") as f:
    version_file = f.read()

version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)

if version_match:
    version = version_match.group(1)
else:
    raise RuntimeError("Unable to find version string.")


# --- README Handling ---
# Read the contents of the README.md file to use as the long description for PyPI.
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


# --- Setup Configuration ---
setup(
    # --- Core Package Metadata ---
    name="pyfwg",
    version=version,

    # --- Author Information ---
    author="Daniel Sánchez-García",
    author_email="daniel.sanchezgarcia@uca.es",

    # --- Descriptions ---
    description="A Python workflow manager for the Future Weather Generator tool.",
    long_description=long_description,
    long_description_content_type="text/markdown",

    # --- Project URLs ---
    url="https://github.com/dsanchez-garcia/pyfwg",
    project_urls={
        "Bug Tracker": "https://github.com/dsanchez-garcia/pyfwg/issues",
        "Documentation": "https://pyfwg.readthedocs.io/",
    },

    # --- License and Classifiers ---
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
    ],

    # --- Package Finding and Data ---
    packages=find_packages(exclude=["wip", "wip.*", "tests", "tests.*"]),
    include_package_data=True,

    # --- Dependencies and Requirements ---
    python_requires=">=3.8",
    install_requires=[
        'importlib_resources; python_version<"3.9"',
    ],
    extras_require={
        "colors": ["colorlog"],
        "docs": [
            "sphinx",
            "sphinx-rtd-theme",
            "nbsphinx",
        ],
        "iterator": ["pandas"],
        # Define un extra 'all' que instala todo
        "all": [
            "colorlog",
            "pandas",
        ]
    },
)