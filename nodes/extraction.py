import logging
from pathlib import Path

from utils.pdf_utils import extract_with_pymupdf, extract_with_pdfplumber, extract_with_pypdf2
from models.state import PipelineState

def extraction_node(state: PipelineState) -> PipelineState:
    """
    Nodo 2: Extracción de Texto
    
    Funciones:
    - Extracción de las primeras 3 páginas
    - Preservación de metadatos de página
    """

    logger = logging.getLogger("Nodo 2")
    logger.info("Iniciando extracción de texto")
    
    state = state.update_stage('Extracción')
    file_path = Path(state.document_info.file_path or "")
    
    # Obtener método de extracción ya validado del nodo 1
    extraction_method = state.logging.debug_info.get("extraction_method", "PyMuPDF")
    max_pages = 3
    
    logger.info(f"Usando método de extracción validado: {extraction_method}")
    
    # Mapeo de métodos a funciones
    extraction_strategies = {
        "PyMuPDF": extract_with_pymupdf,
        "pdfplumber": extract_with_pdfplumber,
        "PyPDF2": extract_with_pypdf2
    }
    
    try:
        # Usar directamente el método que ya funcionó en validación
        extraction_func = extraction_strategies.get(extraction_method)
        if not extraction_func:
            logger.error(f"Método de extracción no reconocido: {extraction_method}")
            return state.add_error(f"Método de extracción inválido: {extraction_method}")
        
        # Extraer texto con el método validado
        raw_text, page_data = extraction_func(file_path, max_pages)
        
        if not raw_text.strip():
            logger.warning("No se extrajo texto del documento")
            return state.add_error("El documento no contiene texto extraíble")
        
        # Actualizar estado con texto extraído
        state.text_content.raw_text = raw_text
        total_chars = len(raw_text.strip())
        
        # Actualizar logging.debug_info con estadísticas de extracción
        state.logging.debug_info.update({
            "text_extraction_method": extraction_method,  # Usar el método real
            "max_pages_processed": max_pages,
            "total_characters": total_chars,
            "pages_with_text": len(page_data),
            "page_data": page_data,
            "extraction_successful": True
        })
        
        logger.info(f"Extracción completada con {extraction_method}: {total_chars} caracteres, {len(page_data)} páginas")
        state = state.add_message(f"Texto extraído: {total_chars} caracteres de {len(page_data)} páginas")
        
        print(state.text_content.raw_text)
        print("=======================")
        print(len(state.text_content.raw_text))
        return state
        
    except ImportError as e:
        logger.error(f"Biblioteca de extracción no disponible: {e}")
        return state.add_error(f"Error de dependencia: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error durante extracción de texto: {e}")
        return state.add_error(f"Error extrayendo texto: {str(e)}")