# InvoiceProcessing – Pipeline de facturas con IA

Pipeline para procesar facturas en PDF, extraer sus datos con LLM y entregarlos listos para guardar o exportar a Excel. Incluye API (FastAPI), frontend ligero y un pipeline orquestado con LangGraph.

## ¿Qué hace?

- Valida y lee un PDF de factura (hasta 10 MB).
- Extrae texto de las primeras páginas usando PyMuPDF/pdfplumber/PyPDF2 según disponibilidad.
- Limpia y normaliza el texto.
- Usa un LLM (OpenAI) con prompts especializados para facturas peruanas y retorna un JSON con: datos del cliente, items, forma de pago, moneda, subtotal, IGV, total y detracción.
- Permite descargar un Excel con el resultado y guardar en PostgreSQL (opcional).

## Stack tecnológico

- Backend: FastAPI, Uvicorn
- Orquestación: LangGraph (StateGraph + MemorySaver)
- LLM: OpenAI (gpt-4o-mini por defecto)
- PDF: PyMuPDF (fitz), pdfplumber, PyPDF2
- Datos/Validación: Pydantic, pydantic-settings
- DB: asyncpg (PostgreSQL) – opcional
- Excel: openpyxl
- Frontend: HTML/CSS/JS vanilla
- Contenedor: Docker (multi-stage)

## Arquitectura y flujo del pipeline

Archivo: `pipeline.py` (LangGraph)

Flujo secuencial de nodos:
1) document_ingestion → 2) text_extraction → 3) text_cleaning → 4) llm → END

Nodos (carpeta `nodes/`):
- Nodo 1 – Ingesta (`ingestion.py`)
	- Valida existencia, tamaño (<= settings.max_pdf_size_mb), integridad del PDF y que tenga texto extraíble.
	- Determina el método de extracción más fiable (PyMuPDF/pdfplumber/PyPDF2) y deja metadata en `logging.debug_info`.
- Nodo 2 – Extracción (`extraction.py`)
	- Extrae texto de hasta 3 páginas con el método validado.
	- Guarda texto crudo en `state.text_content.raw_text` y estadísticas.
- Nodo 3 – Limpieza (`cleaning.py`)
	- Normaliza mayúsculas y espacios; calcula métricas de limpieza.
	- Guarda el texto limpio en `state.text_content.cleaned_text`.
- Nodo 4 – LLM (`llm.py`)
	- Genera prompts (`models/prompts.py`) y llama a OpenAI.
	- Parsea el JSON y lo pone en `state.extracted_data`. Actualiza métricas y marca `status=COMPLETED`.

## El State del pipeline

Modelo principal: `models/state.py` (Pydantic)
- document_info: file_path, filename, file_size
- text_content: raw_text, cleaned_text
- processing_control: processing_stage, status (PROCESSING/COMPLETED/FAILED)
- metrics: tokens_used, processing_time, cost_estimate, llm_model
- quality: confidence_score, completeness_score
- logging: messages, errors, warnings, debug_info
- extracted_data: dict con el resultado del LLM (cliente, items, totales, detracción)

Configuración: `models/settings.py`
- Lee `.env`. Requiere variables: `OPENAI_API_KEY` y `DATABASE_URL` (si usarás DB).
- Otros: `llm_model`, `llm_temperature`, límites de PDF, etc.

## API (FastAPI)

Archivo: `main.py`
- POST /upload: Subir PDF. Devuelve `job_id` y estado inicial. El proceso corre en background.
- GET /status/{job_id}: Estado del job (PENDING/PROCESSING/COMPLETED/FAILED).
- GET /result/{job_id}: Resultado completo cuando está COMPLETED.
- POST /guardar-factura: Guarda en PostgreSQL la factura recibida desde el frontend. Requiere DB.
- POST /guardar-factura-excel: Genera y descarga un Excel con los datos enviados.
- GET /facturas: Lista facturas guardadas (paginado). Requiere DB.

Notas:
- La app puede iniciar sin DB; los endpoints de guardado/listado retornarán 503 si no hay conexión.
- El Dockerfile define un healthcheck a `/health`; agrega ese endpoint si lo necesitas o ajusta el healthcheck.

## Frontend ligero

Ruta: `frontend/`
- `index.html`: interfaz con arrastrar/soltar o selección de PDF, barra de progreso y formulario editable.
- `script.js`: llama a la API (`/upload`, `/status`, `/result`) y completa el formulario con `extracted_data`. Permite descargar Excel con `/guardar-factura-excel`.
- `styles.css`: estilos modernos y responsivos.

Uso: abre `frontend/index.html` en el navegador con el backend levantado en `http://localhost:8000` (CORS habilitado para dev).

## Requisitos y configuración

Prerrequisitos:
- Python 3.11+
- Clave de OpenAI (formato `sk-...`)
- PostgreSQL (opcional, para persistencia)

Archivo `.env` mínimo en la raíz:
```
OPENAI_API_KEY=sk-XXXX
DATABASE_URL=postgresql://user:pass@host:5432/dbname  # opcional si no usarás DB
TEMP_DIR=./temp
LLM_MODEL=gpt-4o-mini
```

## Ejecución local (Windows PowerShell)

Instalar dependencias y levantar API:
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abrir el frontend:
- Doble clic en `frontend/index.html` o sirvelo con un servidor estático.

## Docker

Build y run:
```powershell
docker build -t invoice-processing:latest .
docker run -e OPENAI_API_KEY=sk-XXXX -e DATABASE_URL=postgresql://user:pass@host:5432/dbname -p 8000:8000 invoice-processing:latest
```

## Estructura de carpetas (resumen)

```
.
├── main.py                # API FastAPI
├── pipeline.py            # Orquestación LangGraph
├── database.py            # Gestor async de PostgreSQL (opcional)
├── models/                # State, settings, prompts
├── nodes/                 # Nodos: ingestion, extraction, cleaning, llm
├── utils/                 # PDF, LLM, Excel, API helpers
├── frontend/              # UI simple (HTML/JS/CSS)
├── requirements.txt       # Dependencias
├── Dockerfile             # Imagen para despliegue
└── temp/                  # Archivos temporales
```

## Notas y límites

- Se procesan hasta 3 páginas por PDF en la extracción actual (ajustable).
- El LLM responde solo con JSON; si el PDF no tiene texto extraíble, el job falla con mensaje claro.
- Para persistencia se asume un esquema con tablas `facturas` y `factura_items` (crear antes de usar `guardar-factura`).

—
Autor: LeonAchataS · Proyecto: InvoiceProcessing
