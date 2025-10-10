from pathlib import Path
from fastapi import UploadFile, HTTPException
import uuid


def validate_pdf(file: UploadFile, max_size_mb: int) -> bytes:
    """
    Valida que el archivo subido sea un PDF válido y cumple con las restricciones de tamaño.

    Args:
        file: Archivo subido por el usuario.
        max_size_mb: Tamaño máximo permitido en MB.

    Returns:
        El contenido del archivo en bytes.

    Raises:
        HTTPException: Si el archivo no es válido.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo debe tener un nombre")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    file_content = file.file.read()

    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande: {file_size_mb:.1f}MB. Máximo permitido: {max_size_mb}MB"
        )

    if not file_content.startswith(b'%PDF'):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF válido")

    return file_content


def save_temp_file(file_content: bytes, filename: str, temp_dir: Path) -> Path:
    """
    Guarda el contenido del archivo en un archivo temporal.

    Args:
        file_content: Contenido del archivo en bytes.
        filename: Nombre original del archivo.
        temp_dir: Directorio temporal donde guardar el archivo.

    Returns:
        La ruta al archivo temporal creado.
    """
    temp_dir.mkdir(exist_ok=True)
    temp_filename = f"upload_{uuid.uuid4().hex}_{filename}"
    temp_file_path = temp_dir / temp_filename

    with open(temp_file_path, 'wb') as temp_file:
        temp_file.write(file_content)

    return temp_file_path