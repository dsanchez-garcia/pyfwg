# pyfwg/__init__.py
"""
pyfwg: Python Future Weather Generator

This file serves as the main entry point for the pyfwg package.
It defines the public API by importing the key classes, functions, and
constants from the various modules. This allows users to access all primary
features directly from the top-level `pyfwg` import.

pyfwg does not configure logging when it is imported. Its modules log to the
'pyfwg' logger, whose messages are shown if the application configures logging
(e.g., with `logging.basicConfig`). In notebooks and scripts that do not, call
`pyfwg.enable_console_logging()` to print them on the console.
"""

import logging
from typing import Optional, TextIO, Union

# --- Logging Configuration ---
# As recommended for libraries, the package logger only gets a NullHandler.
# The handlers and levels of the application (e.g., of the root logger) are not
# modified.
logging.getLogger(__name__).addHandler(logging.NullHandler())


def enable_console_logging(level: Union[int, str] = logging.INFO,
                           color: bool = True,
                           stream: Optional[TextIO] = None) -> logging.Handler:
    """Prints the log messages of pyfwg on the console.

    pyfwg does not configure logging when it is imported, so its messages
    (progress, validation errors, etc.) are only shown if the application
    configures logging. This helper is meant for notebooks and scripts that do
    not: it adds a console handler to the 'pyfwg' logger and sets the level of
    that logger. Other loggers, including the root logger, are not modified.

    The messages are colored by level if the optional `colorlog` package is
    installed. Calling the function again replaces the handler added before,
    so messages are not duplicated when a notebook cell is run again.

    If the application already logs to the console (e.g., with
    `logging.basicConfig`), this function is not needed: the messages of pyfwg
    propagate to its handlers, and their level can be set with
    `logging.getLogger('pyfwg').setLevel(logging.INFO)`.

    Args:
        level (Union[int, str], optional): Minimum level of the messages to
            show (e.g., `logging.INFO` or 'WARNING'). Defaults to `logging.INFO`.
        color (bool, optional): If True, colors the messages when `colorlog`
            is installed. Defaults to True.
        stream (Optional[TextIO], optional): Stream to write the messages to.
            Defaults to None, which uses `sys.stderr`.

    Returns:
        logging.Handler: The handler that was added. It can be removed with
        `logging.getLogger('pyfwg').removeHandler(handler)`.
    """
    package_logger = logging.getLogger(__name__)
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    handler = None
    if color:
        try:
            import colorlog
            handler = colorlog.StreamHandler(stream)
            handler.setFormatter(colorlog.ColoredFormatter(
                '%(log_color)s' + log_format,
                datefmt=date_format,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'bold_red',
                }
            ))
        except ImportError:
            # colorlog is optional: fall back to plain messages.
            handler = None
    if handler is None:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    # Mark the handler so that a later call can replace it.
    handler._pyfwg_console_handler = True

    for existing_handler in list(package_logger.handlers):
        if getattr(existing_handler, '_pyfwg_console_handler', False):
            package_logger.removeHandler(existing_handler)
    package_logger.addHandler(handler)
    package_logger.setLevel(level)
    return handler


# --- Public API Definition ---

# Define the official version of the library.
__version__ = "0.4.0"

# Import the main classes for the advanced, step-by-step workflows.
# This makes them accessible as `pyfwg.MorphingWorkflowGlobal`.
from .workflow import MorphingWorkflowGlobal, MorphingWorkflowEurope, MorphingWorkflowCordex

# Import the iterator class for running multiple morphing scenarios.
from .iterator import MorphingIterator

# Import the high-level convenience functions for direct, one-shot usage.
# This makes them accessible as `pyfwg.morph_epw_global`.
from .api import morph_epw_global, morph_epw_europe, morph_epw_cordex

# Import utility functions that are useful for users, such as pre-flight checks.
# This makes them accessible as `pyfwg.check_lcz_availability`.
from .utils import (
    uhi_morph,
    check_lcz_availability,
    copy_tutorials,
    get_available_lczs,
    export_template_to_excel,
    load_runs_from_excel,
    detect_fwg_version,
    detect_fwg_tool,
    get_fwg_cli_style,
    get_fwg_distribution_info,
    sanitize_epw_minutes,
    get_fwg_parameters_info
)

# Expose important constants so users can easily access lists of valid models and scenarios.
# This makes them accessible as `pyfwg.DEFAULT_GLOBAL_GCMS`.
from .constants import (
    DEFAULT_GLOBAL_GCMS,
    DEFAULT_EUROPE_RCMS,
    DEFAULT_CORDEX_RCMS,
    CORDEX_REGIONS,
    GLOBAL_SCENARIOS,
    EUROPE_SCENARIOS,
    CORDEX_SCENARIOS,
    ALL_POSSIBLE_YEARS
)