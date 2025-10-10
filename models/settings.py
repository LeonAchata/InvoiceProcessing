from typing import Dict
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    """Configuración principal del sistema """
    
    # === API KEYS (REQUERIDAS) ===
    openai_api_key: str = Field(..., description="OpenAI API key")
    
    # === CONFIGURACIÓN DE BASE DE DATOS ===
    database_url: str = Field(
        ..., 
        description="PostgreSQL connection string (postgresql://user:pass@host:port/dbname)"
    )
    
    # === CONFIGURACIÓN DE PROCESAMIENTO ===
    max_tokens_per_chunk: int = Field(default=2500, description="Máximo tokens por chunk")
    max_tokens_total: int = Field(default=5000, description="Máximo tokens total")
    chunk_overlap: int = Field(default=250, description="Solapamiento entre chunks")
    
    # === CONFIGURACIÓN DE CALIDAD ===
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Umbral de confianza")
    completeness_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Umbral de completitud")
    
    # === CONFIGURACIÓN DE ARCHIVOS ===
    max_pdf_size_mb: int = Field(default=10, gt=0, le=100, description="Tamaño máximo PDF en MB")
    temp_dir: str = Field(default="./temp", description="Directorio temporal")
    
    # === CONFIGURACIÓN DE LLM ===
    llm_model: str = Field(default="gpt-4o-mini", description="Modelo OpenAI a usar")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="Temperatura del modelo")
    max_retries: int = Field(default=3, ge=1, le=10, description="Máximo reintentos")
    request_timeout: int = Field(default=120, ge=30, le=300, description="Timeout en segundos")
    
    # === CONFIGURACIÓN DE CHUNKS ===
    priority_zone_tokens: int = Field(default=1500, description="Tokens zona alta prioridad")
    standard_zone_tokens: int = Field(default=2500, description="Tokens zona media prioridad")
    low_priority_tokens: int = Field(default=3000, description="Tokens zona baja prioridad")
    
    # === CONFIGURACIÓN DE LOGGING ===
    log_level: str = Field(default="INFO", description="Nivel de logging")
    enable_file_logging: bool = Field(default=True, description="Habilitar logging a archivo")
    log_file_path: str = Field(default="insurance_processor.log", description="Ruta del archivo de log")
    
    # === CONFIGURACIÓN DE DESARROLLO ===
    debug_mode: bool = Field(default=False, description="Modo debug")
    save_intermediate_results: bool = Field(default=False, description="Guardar resultados intermedios")
    cache_enabled: bool = Field(default=True, description="Cache habilitado")
    
    openai_pricing: Dict[str, Dict[str, float]] = Field(
        default={
            "gpt-4o": {"input": 0.0025, "output": 0.01},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002}
        },
        description="Precios de modelos OpenAI para cálculo de costos"
    )
    
    # Configuración del modelo
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # === VALIDATORS ===
    
    @field_validator('openai_api_key', mode='before')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        if not v or not v.startswith("sk-"):
            raise ValueError("OpenAI API key debe comenzar con 'sk-'")
        return v
    
    @field_validator('database_url', mode='before')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validar URL de PostgreSQL."""
        if not v or not v.startswith("postgresql://"):
            raise ValueError("Database URL debe comenzar con 'postgresql://'")
        return v

    @field_validator('temp_dir', mode='before')
    @classmethod
    def validate_temp_dir(cls, v: str) -> str:
        """Crear directorio temporal si no existe."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator('log_level', mode='before')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validar nivel de logging."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level debe ser uno de: {valid_levels}")
        return v.upper()

# Instancia global de configuración
settings = Settings()