"""
API FastAPI escalable para el procesador de PDFs de facturas.
Endpoints separados para upload asíncrono y consulta de resultados.
"""

import logging
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import os

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Importar pipeline y configuraciones
from pipeline import Pipeline
from models.settings import settings
from utils.api_utils import validate_pdf, save_temp_file
from utils.excel_utils import generar_excel_factura
from database import DatabaseManager

# Crear app FastAPI
app = FastAPI(
    title="Procesador de facturas",
    description="API escalable para procesar PDFs de facturas",
    version="2.0.0"
)

# Configurar CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios exactos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# INSTANCIAS GLOBALES
# ================================

job_storage = {}  # {job_id: job_data}
pipeline = Pipeline()
db_manager = None  # Se inicializa en startup

class JobStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# ================================
# EVENTOS DE LIFECYCLE
# ================================

@app.on_event("startup")
async def startup_event():
    """Inicializar conexiones al arrancar la aplicación."""
    global db_manager
    
    try:
        db_manager = DatabaseManager(settings.database_url)
        await db_manager.conectar()
        logger.info("Conexión a base de datos establecida")
    except Exception as e:
        logger.error(f"Error conectando a base de datos: {e}")
        logger.warning("La aplicación continuará sin conexión a BD")

@app.on_event("shutdown")
async def shutdown_event():
    """Cerrar conexiones al apagar la aplicación."""
    if db_manager:
        await db_manager.cerrar_conexion()
        logger.info("Conexión a base de datos cerrada")

# ================================
# FUNCIONES AUXILIARES
# ================================

def create_job_id() -> str:
    """Genera un ID único para el trabajo."""
    return str(uuid.uuid4())

async def process_file_background(job_id: str, file_path: str, filename: str):
    """Procesa el archivo en background y actualiza el estado."""
    try:
        logger.info(f"[{job_id}] Iniciando procesamiento de: {filename}")
        
        # Actualizar estado a PROCESSING
        job_storage[job_id].update({
            "status": JobStatus.PROCESSING,
            "started_at": datetime.now().isoformat()
        })

        # Procesar archivo con el pipeline
        result = await pipeline.process(file_path=file_path, filename=filename)
        
        # Actualizar con resultado exitoso
        job_storage[job_id].update({
            "status": JobStatus.COMPLETED,
            "completed_at": datetime.now().isoformat(),
            "result": result,
            "filename": filename  # Guardar filename para uso posterior
        })
        
        logger.info(f"[{job_id}] Procesamiento completado exitosamente")
        
    except Exception as e:
        logger.error(f"[{job_id}] Error en procesamiento: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Actualizar con error
        job_storage[job_id].update({
            "status": JobStatus.FAILED,
            "completed_at": datetime.now().isoformat(),
            "error": str(e)
        })
    
    finally:
        # Limpiar archivo temporal
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"[{job_id}] Archivo temporal eliminado: {file_path}")
        except Exception as e:
            logger.error(f"[{job_id}] Error eliminando archivo: {e}")

# ================================
# ENDPOINTS - PROCESAMIENTO
# ================================

@app.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Endpoint para subir PDF y iniciar procesamiento asíncrono.
    
    Args:
        file: Archivo PDF de la factura
        
    Returns:
        Dict con job_id y estado inicial
    """
    try:
        # Validar archivo PDF
        file_content = validate_pdf(file, settings.max_pdf_size_mb)

        # Crear job ID único
        job_id = create_job_id()
        
        # Guardar archivo temporal
        temp_file_path = save_temp_file(file_content, file.filename, Path(settings.temp_dir))
        logger.info(f"[{job_id}] Archivo guardado: {temp_file_path}")

        # Validar que el archivo existe
        if not temp_file_path.exists():
            raise HTTPException(status_code=400, detail="El archivo no se pudo guardar correctamente.")

        # Crear entrada en job_storage
        job_storage[job_id] = {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "filename": file.filename,
            "file_size_mb": round(len(file_content) / (1024 * 1024), 2),
            "created_at": datetime.now().isoformat(),
            "file_path": str(temp_file_path)
        }

        # Iniciar procesamiento en background
        background_tasks.add_task(
            process_file_background,
            job_id,
            str(temp_file_path),
            file.filename
        )
        
        logger.info(f"[{job_id}] Job creado para: {file.filename}")

        return {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "message": "Archivo subido exitosamente. Procesamiento iniciado.",
            "filename": file.filename,
            "estimated_time_seconds": 30
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/status/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Consulta el estado de un trabajo de procesamiento.
    
    Args:
        job_id: ID del trabajo
        
    Returns:
        Dict con estado actual del trabajo
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage[job_id]
    
    response = {
        "job_id": job_id,
        "status": job_data["status"],
        "filename": job_data["filename"],
        "created_at": job_data["created_at"]
    }
    
    # Agregar campos específicos según el estado
    if job_data["status"] == JobStatus.PROCESSING and "started_at" in job_data:
        response["started_at"] = job_data["started_at"]
    
    elif job_data["status"] == JobStatus.COMPLETED:
        response.update({
            "completed_at": job_data["completed_at"],
            "result_available": True
        })
    
    elif job_data["status"] == JobStatus.FAILED:
        response.update({
            "completed_at": job_data["completed_at"],
            "error": job_data["error"]
        })
    
    return response


@app.get("/result/{job_id}")
async def get_job_result(job_id: str) -> Dict[str, Any]:
    """
    Obtiene el resultado completo de un trabajo completado.
    
    Args:
        job_id: ID del trabajo
        
    Returns:
        Dict con resultado completo del procesamiento
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage[job_id]
    
    if job_data["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"El trabajo está en estado '{job_data['status']}'. Solo trabajos COMPLETED tienen resultados."
        )
    
    result = job_data["result"].copy()
    
    # Agregar metadata del job
    result["job_metadata"] = {
        "job_id": job_id,
        "filename": job_data["filename"],
        "file_size_mb": job_data["file_size_mb"],
        "created_at": job_data["created_at"],
        "completed_at": job_data["completed_at"]
    }
    
    return result

# ================================
# ENDPOINTS - BASE DE DATOS
# ================================

@app.post("/guardar-factura")
async def guardar_factura(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarda factura procesada en PostgreSQL.
    
    Args:
        datos: Diccionario con datos de la factura (formato del frontend)
    
    Returns:
        Dict con confirmación y factura_id
    
    Raises:
        HTTPException: Si hay error guardando o BD no disponible
    """
    if not db_manager:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible. Verifica la configuración."
        )
    
    try:
        # Obtener filename del último job procesado (opcional)
        filename = datos.get('_filename')  # El frontend puede enviarlo
        
        # Guardar en base de datos
        factura_id = await db_manager.guardar_factura(datos, filename)
        
        logger.info(f"Factura guardada exitosamente con ID: {factura_id}")
        
        return {
            "success": True,
            "factura_id": factura_id,
            "message": f"Factura #{factura_id} guardada exitosamente"
        }
    
    except Exception as e:
        logger.error(f"Error guardando factura: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar: {str(e)}"
        )


@app.post("/guardar-factura-excel")
async def guardar_factura_excel(datos: Dict[str, Any]) -> StreamingResponse:
    """
    Genera y descarga un archivo Excel con los datos de la factura.
    
    Args:
        datos: Diccionario con datos de la factura (formato del frontend)
    
    Returns:
        StreamingResponse: Archivo Excel para descarga
    
    Raises:
        HTTPException: Si hay error generando el Excel
    """
    try:
        # Obtener filename del último job procesado (opcional)
        filename = datos.get('_filename', 'factura_procesada.pdf')
        
        # Generar Excel
        excel_buffer = generar_excel_factura(datos, filename)
        
        # Generar nombre de archivo Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f"factura_{timestamp}.xlsx"
        
        logger.info(f"Excel generado: {excel_filename}")
        
        # Retornar como descarga
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={excel_filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Error generando Excel: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar Excel: {str(e)}"
        )


@app.get("/facturas")
async def listar_facturas(limite: int = 50, offset: int = 0) -> Dict[str, Any]:
    """
    Lista facturas guardadas con paginación.
    
    Args:
        limite: Cantidad máxima de registros (default: 50)
        offset: Registros a saltar (default: 0)
    
    Returns:
        Lista de facturas
    """
    if not db_manager:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible"
        )
    
    try:
        facturas = await db_manager.listar_facturas(limite, offset)
        
        return {
            "total": len(facturas),
            "facturas": facturas,
            "limite": limite,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"Error listando facturas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/facturas/{factura_id}")
async def obtener_factura(factura_id: int) -> Dict[str, Any]:
    """
    Obtiene una factura específica con sus items.
    
    Args:
        factura_id: ID de la factura
    
    Returns:
        Factura completa con items
    """
    if not db_manager:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible"
        )
    
    try:
        factura = await db_manager.obtener_factura(factura_id)
        
        if not factura:
            raise HTTPException(
                status_code=404,
                detail=f"Factura {factura_id} no encontrada"
            )
        
        return factura
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo factura: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# ENDPOINTS - UTILIDADES
# ================================

@app.get("/jobs")
async def list_jobs(limit: int = 10) -> Dict[str, Any]:
    """
    Lista los trabajos recientes (útil para debugging).
    
    Args:
        limit: Número máximo de trabajos a retornar
        
    Returns:
        Lista de trabajos con información básica
    """
    jobs = list(job_storage.values())
    
    # Ordenar por fecha de creación (más recientes primero)
    jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    # Limitar cantidad
    jobs = jobs[:limit]
    
    # Simplificar información para la lista
    simplified_jobs = []
    for job in jobs:
        simplified = {
            "job_id": job["job_id"],
            "status": job["status"],
            "filename": job["filename"],
            "created_at": job["created_at"]
        }
        
        if job["status"] == JobStatus.COMPLETED:
            simplified["completed_at"] = job["completed_at"]
        elif job["status"] == JobStatus.FAILED:
            simplified["error"] = job.get("error", "Unknown error")
            
        simplified_jobs.append(simplified)
    
    return {
        "total_jobs": len(job_storage),
        "jobs": simplified_jobs
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, Any]:
    """
    Elimina un trabajo del almacenamiento.
    
    Args:
        job_id: ID del trabajo a eliminar
        
    Returns:
        Confirmación de eliminación
    """
    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job ID no encontrado")
    
    job_data = job_storage.pop(job_id)
    
    # Limpiar archivo si aún existe
    if "file_path" in job_data and os.path.exists(job_data["file_path"]):
        try:
            os.unlink(job_data["file_path"])
            logger.info(f"Archivo eliminado: {job_data['file_path']}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo: {e}")
    
    return {
        "message": f"Job {job_id} eliminado exitosamente",
        "deleted_job": {
            "job_id": job_id,
            "filename": job_data["filename"],
            "status": job_data["status"]
        }
    }

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Endpoint de salud para monitoreo."""
    db_healthy = await db_manager.verificar_conexion() if db_manager else False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "database": "connected" if db_healthy else "disconnected",
        "active_jobs": len([j for j in job_storage.values() if j["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]]),
        "total_jobs": len(job_storage),
        "version": "2.0.0"
    }


@app.get("/estadisticas")
async def obtener_estadisticas() -> Dict[str, Any]:
    """
    Obtiene estadísticas de facturas guardadas.
    
    Returns:
        Métricas agregadas de facturas
    """
    if not db_manager:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible"
        )
    
    try:
        stats = await db_manager.obtener_estadisticas()
        return stats
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Configuración para desarrollo
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )