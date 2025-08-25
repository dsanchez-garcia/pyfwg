# setup.py

from setuptools import setup, find_packages

# Lee el contenido de tu archivo README.md para la descripción larga
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    # --- Información Esencial ---
    name="pyfwg",
    version="0.1.1",

    # --- Autores ---
    author="Daniel Sánchez-García",
    author_email="daniel.sanchezgarcia@uca.es",

    # --- Descripciones ---
    description="A Python workflow manager for the FutureWeatherGenerator tool.",
    long_description=long_description,
    long_description_content_type="text/markdown", # Importante para que PyPI renderice el Markdown

    # --- Licencia y Clasificadores ---
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
    ],

    # --- Requisitos de Python ---
    python_requires=">=3.9",

    # --- Dónde encontrar el código ---
    # Esto buscará automáticamente el paquete 'pyfwg' en tu proyecto.
    # Funciona tanto para la estructura con 'src/' como para la estructura plana.
    packages=find_packages(),

    # --- URLs del Proyecto ---
    url="https://github.com/dsanchez-garcia/pyfwg",
    project_urls={
        "Bug Tracker": "https://github.com/dsanchez-garcia/pyfwg/issuespip install twine --upgrade",
    },

    # --- Dependencias ---
    # No hay dependencias de ejecución, pero sí de documentación
    extras_require={
        "docs": [
            "sphinx",
            "sphinx-rtd-theme",
            "nbsphinx",
        ]
    },
)