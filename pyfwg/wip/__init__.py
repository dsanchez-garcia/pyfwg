# pyfwg/__init__.py
"""
pyfwg: Python Future Weather Generator

This file serves as the main entry point for the pyfwg package.
It handles the initial setup, such as configuring the logging system with
optional color support, and it defines the public API by importing the key
classes, functions, and constants from the various modules. This allows users
to access all primary features directly from the top-level `pyfwg` import.
"""

import logging

# --- Colored Logging Configuration ---
# This block attempts to configure colored logging using the 'colorlog' library.
# If 'colorlog' is not installed, it gracefully falls back to the standard,
# non-colored logging setup, ensuring the library remains functional.
try:
    # Attempt to import the optional colorlog library.
    import colorlog

    # Get the root logger.
    logger = colorlog.getLogger()

    # If the logger already has handlers (e.g., from an interactive console like
    # IPython or Jupyter), we remove them to ensure a clean slate. This makes
    # our custom colored handler the one and only handler.
    if logger.hasHandlers():
        logger.handlers.clear()

    # If the logger already has handlers, it might have been configured already.
    # This check prevents adding duplicate handlers in some environments (e.g., Jupyter).
    if not logger.handlers:
        # Create a handler that outputs to the console stream.
        handler = colorlog.StreamHandler()

        # Create a formatter that adds color codes to the log output.
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            # Define the color for each log level.
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        )

        # Set the custom formatter on the handler.
        handler.setFormatter(formatter)

        # Add the configured handler to the root logger.
        logger.addHandler(handler)
        # Set the default logging level for the library.
        logger.setLevel(logging.INFO)

except ImportError:
    # If colorlog is not installed, fall back to the standard basicConfig.
    # This ensures the library works correctly even without the optional dependency.
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# --- Public API Definition ---

# Define the official version of the library.
__version__ = "0.2.0"

# Import the main classes for the advanced, step-by-step workflows.
# This makes them accessible as `pyfwg.MorphingWorkflowGlobal`.
from .workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope

# Import the high-level convenience functions for direct, one-shot usage.
# This makes them accessible as `pyfwg.morph_epw_global`.
from .api import morph_epw_global, morph_epw_europe

# Import utility functions that are useful for users, such as pre-flight checks.
# This makes them accessible as `pyfwg.check_lcz_availability`.
from .utils import uhi_morph, check_lcz_availability

# Expose important constants so users can easily access lists of valid models and scenarios.
# This makes them accessible as `pyfwg.DEFAULT_GLOBAL_GCMS`.
from .constants import (
    DEFAULT_GLOBAL_GCMS,
    DEFAULT_EUROPE_RCMS,
    GLOBAL_SCENARIOS,
    EUROPE_SCENARIOS,
    ALL_POSSIBLE_YEARS
)