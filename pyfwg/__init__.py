# pyfwg/__init__.py

# Define la versión de la librería para que sea accesible
__version__ = "0.1.0"

# Importa la clase principal para que los usuarios puedan hacer:
# from pyfwg import MorphingWorkflow
from .workflow import MorphingWorkflow

# Opcionalmente, también puedes exponer las constantes
from .constants import DEFAULT_GCMS, ALL_POSSIBLE_SCENARIOS, ALL_POSSIBLE_YEARS