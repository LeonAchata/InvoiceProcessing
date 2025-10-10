from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict
import datetime

# === MODELOS AUXILIARES ===

class ProcessingMetrics(BaseModel):
    """Métricas de procesamiento."""
    tokens_used: int = Field(default=0, description="Tokens utilizados")
    processing_time: float = Field(default=0.0, description="Tiempo de procesamiento en segundos")
    cost_estimate: float = Field(default=0.0, description="Costo estimado en USD")
    llm_model: str = Field(default = "gpt-4o-mini", description='Modelo de Open AI')
    
class QualityMetrics(BaseModel):
    """Métricas de calidad."""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Score de confianza")
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Score de completitud")

class DocumentInfo(BaseModel):
    """Información del documento."""
    document_input: Dict[str, Any] = Field(default_factory=dict)
    file_path: str = Field(default="", description="Ruta del archivo")
    filename: str = Field(default="", description="Nombre del archivo")
    file_size: int = Field(default=0, description="Tamaño del archivo en bytes")

class TextContent(BaseModel):
    """Contenido de texto extraído."""
    raw_text: Optional[str] = Field(default=None, description="Texto crudo extraído")
    cleaned_text: Optional[str] = Field(default=None, description="Texto limpio")

class ProcessingControl(BaseModel):
    """Control de flujo del procesamiento."""
    processing_stage: str = Field(default="ingestion", description="Etapa actual de procesamiento")
    status: str = Field(default="PROCESSING", description="Estado del procesamiento")

class LoggingData(BaseModel):
    """Datos de logging y debug."""
    messages: List[str] = Field(default_factory=list, description="Mensajes del proceso")
    errors: List[str] = Field(default_factory=list, description="Errores encontrados")
    warnings: List[str] = Field(default_factory=list, description="Warnings generados")
    debug_info: Dict[str, Any] = Field(default_factory=dict, description="Información de debug")

# === MODELO PRINCIPAL ===

class PipelineState(BaseModel):
    """
    Estado completo del pipeline de procesamiento.
    """
    
    model_config = ConfigDict(
        extra='allow',
        validate_assignment=True,
        use_enum_values=True,
        populate_by_name=True
    )
    
    # === COMPOSICIÓN DE MODELOS ===
    document_info: DocumentInfo = Field(default_factory=DocumentInfo)
    text_content: TextContent = Field(default_factory=TextContent)
    processing_control: ProcessingControl = Field(default_factory=ProcessingControl)
    metrics: ProcessingMetrics = Field(default_factory=ProcessingMetrics)
    quality: QualityMetrics = Field(default_factory=QualityMetrics)
    logging: LoggingData = Field(default_factory=LoggingData)


    extracted_data: Dict[str, Any] = Field(default_factory=dict, description="Datos extraídos por LLM")
    # === PROPIEDADES DE CONVENIENCIA ===
    
    @property
    def status(self) -> str:
        """Acceso directo al status."""
        return self.processing_control.status
    
    @property
    def processing_stage(self) -> str:
        """Acceso directo a la etapa."""
        return self.processing_control.processing_stage
    
    @property
    def confidence_score(self) -> float:
        """Acceso directo al score de confianza."""
        return self.quality.confidence_score
    
    @property
    def completeness_score(self) -> float:
        """Acceso directo al score de completitud."""
        return self.quality.completeness_score
    
    # === MÉTODOS DE ESTADO ===
    
    def update_stage(self, stage: str) -> 'PipelineState':
        """Actualizar etapa de procesamiento."""
        self.processing_control.processing_stage = stage
        return self.add_message(f"Iniciando etapa: {stage}")
    
    def add_message(self, message: str) -> 'PipelineState':
        """Agregar mensaje al estado."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logging.messages.append(f"[{timestamp}] {message}")
        return self
    
    def add_error(self, error: str) -> 'PipelineState':
        """Agregar error al estado."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logging.errors.append(f"[{timestamp}] {error}")
        self.processing_control.status = "FAILED"
        return self
    
    def add_warning(self, warning: str) -> 'PipelineState':
        """Agregar warning al estado."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logging.warnings.append(f"[{timestamp}] {warning}")
        return self
    
    def update_metrics(self, tokens: int = 0, time_delta: float = 0.0) -> 'PipelineState':
        """Actualizar métricas de procesamiento."""
        self.metrics.tokens_used += tokens
        self.metrics.processing_time += time_delta
        
        # Calcular costo estimado (usando precio de gpt-4o-mini)
        input_cost = (tokens / 1000) * 0.00015
        self.metrics.cost_estimate += input_cost
        
        return self
    
    def update_debug_info(self, updates: dict) -> None:
        """
        Actualiza el diccionario debug_info con los valores proporcionados.

        Args:
            updates (dict): Diccionario con las claves y valores a actualizar.
        """
        if not hasattr(self, "debug_info") or not isinstance(self.debug_info, dict):
            self.debug_info = {}
        self.debug_info.update(updates)     
