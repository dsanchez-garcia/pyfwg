# pyfwg/__init__.py

__version__ = "0.1.0"

# Importa la clase principal para el flujo de trabajo avanzado
from .workflow import MorphingWorkflow

# Importa la función de conveniencia para un uso simple pero potente
from .api import morph_epw

# Opcionalmente, también puedes exponer las constantes
from .constants import DEFAULT_GCMS, ALL_POSSIBLE_SCENARIOS, ALL_POSSIBLE_YEARS