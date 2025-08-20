# This module previously provided a standalone CLI interface
# The main functionality is now available via the conda plugin: `conda pypi`
import logging

logger = logging.getLogger(__name__)
logger.info("conda-pypi is now available as a conda plugin. Use: conda pypi --help")
