# pyfwg/__init__.py

__version__ = "0.4.0" # Incrementa la versión

# Importa las clases principales para los flujos de trabajo avanzados
from .workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope

# Importa las funciones de conveniencia de la API
from .api import morph_epw_global, morph_epw_europe

# Importa las funciones de utilidad para que el usuario pueda acceder a ellas
from .utils import uhi_morph, check_lcz_availability

# Expón las constantes
from .constants import (
    DEFAULT_GLOBAL_GCMS,
    DEFAULT_EUROPE_RCMS,
    GLOBAL_SCENARIOS,
    EUROPE_SCENARIOS,
    ALL_POSSIBLE_YEARS
)