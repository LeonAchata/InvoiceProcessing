import logging
from models.state import PipelineState

def cleaning_node(state: PipelineState) -> PipelineState:
    """
    Nodo 3: Limpieza y Normalización de Texto
    
    Funciones:
    - Normalización de espaciado
    """
    
    logger = logging.getLogger("Nodo 3")
    logger.info("Iniciando limpieza de texto")
    
    state = state.update_stage('Limpieza')
    raw_text = state.text_content.raw_text

    if not raw_text:
        logger.warning("No hay texto para limpiar")
        return state.add_warning("No hay texto para limpiar")
    
    original_length = len(raw_text)
    cleaned_text = raw_text.upper()
    
    # === LIMPIEZA BÁSICA ===
    
    # 1. Normalizar espaciado
    import re
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Múltiples espacios → uno
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)  # Múltiples saltos → doble
    
    # 3. Limpiar espacios resultantes
    cleaned_text = cleaned_text.strip()
    
    # === ESTADÍSTICAS DE LIMPIEZA ===
    chars_removed = original_length - len(cleaned_text)
    removal_percentage = (chars_removed / original_length * 100) if original_length > 0 else 0
    
    # === ACTUALIZAR ESTADO ===
    state.text_content.cleaned_text = cleaned_text
    
    # Actualizar logging.debug_info con estadísticas de limpieza
    state.logging.debug_info.update({
        "cleaning_applied": True,
        "characters_removed": chars_removed,
        "removal_percentage": round(removal_percentage, 2),
        "final_text_length": len(cleaned_text),
    })
    
    logger.info(f"Limpieza completada: {chars_removed} caracteres removidos ({removal_percentage:.1f}%)")
    state = state.add_message(f"Texto limpiado: -{chars_removed} caracteres ({removal_percentage:.1f}%)")
    

    print(state.text_content.cleaned_text)
    print("=======================")
    print(len(state.text_content.cleaned_text))
    return state