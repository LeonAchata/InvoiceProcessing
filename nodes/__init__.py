from .ingestion import ingestion_node
from .extraction import extraction_node
from .cleaning import cleaning_node
from .llm import llm_node

import logging

logger = logging.getLogger(__name__)
logger.info(f"Nodos del pipeline inicializados")