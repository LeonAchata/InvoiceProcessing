# Pipeline principal de procesamiento
import logging
import traceback
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import PipelineState, DocumentInfo
from nodes import ingestion_node, extraction_node, cleaning_node, llm_node

logger = logging.getLogger("Pipeline")

class Pipeline:
    
    def __init__(self):
        self.graph = None
        self.app = None
        self.initialize_pipeline()
    
    def initialize_pipeline(self):
        try:
            workflow = StateGraph(PipelineState)
            
            # === AÑADIR NODOS ===
            
            # Fase 1: Ingesta
            workflow.add_node("document_ingestion", ingestion_node)
            workflow.add_node("text_extraction", extraction_node)
            workflow.add_node("text_cleaning", cleaning_node)
            workflow.add_node("llm", llm_node)

            # Punto de entrada
            workflow.set_entry_point("document_ingestion")
            
            # Flujo secuencial
            workflow.add_edge("document_ingestion", "text_extraction")
            workflow.add_edge("text_extraction", "text_cleaning")
            workflow.add_edge("text_cleaning", "llm")
            workflow.add_edge("llm", END)

            # Compilar grafo con memoria
            memory = MemorySaver()
            self.app = workflow.compile(checkpointer=memory)
            
            logger.info("Pipeline inicializado correctamente")
        
        except Exception as e:
            logger.error(f"Error inicializando pipeline: {e}")
            logger.error(traceback.format_exc())
            raise

    async def process(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Procesa un archivo PDF a través del pipeline.

        Args:
            file_path (str): Ruta del archivo PDF a procesar.
            filename (str): Nombre del archivo PDF.

        Returns:
            Dict[str, Any]: Resultado del procesamiento del pipeline.
        """
        try:
            logger.info(f"Iniciando procesamiento de: {filename}")
            
            # === CREAR ESTADO INICIAL ===
            initial_state = self.create_initial_state(file_path, filename)
            logger.info("Ejecutando pipeline")
            
            # Usar un thread_id único para el checkpointer
            import uuid
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            
            # Ejecutar el grafo
            final_state = await self.app.ainvoke(initial_state, config=config)

            result = {
                "processing_control": final_state.get("processing_control"),
                "extracted_data": final_state.get("extracted_data"),
                "metrics": final_state.get("metrics"),
            }

            logger.info(f"Procesamiento completado con los parámetros requeridos.")
            return result
            
        except Exception as e:
            logger.error(f"Error en pipeline: {e}")
            logger.error(traceback.format_exc())
            return None

    def create_initial_state(self, file_path: str, filename: str) -> PipelineState:
        """Crear estado inicial simplificado."""
        
        document_info = DocumentInfo(
            file_path=file_path,
            filename=filename
        )
        
        return PipelineState(document_info=document_info)
