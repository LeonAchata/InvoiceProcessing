# InvoiceProcessing – AI-Powered Invoice Pipeline

AI pipeline to process invoice PDFs, extract data with LLM, and deliver results ready to save or export to Excel. Includes API (FastAPI), lightweight frontend, and a pipeline orchestrated with LangGraph.

## What does it do?

- Validates and reads invoice PDFs (up to 10 MB).
- Extracts text from first pages using PyMuPDF/pdfplumber/PyPDF2 based on availability.
- Cleans and normalizes the text.
- Uses an LLM (OpenAI) with specialized prompts for Peruvian invoices and returns JSON with: customer data, items, payment method, currency, subtotal, VAT (IGV), total, and withholding (detracción).
- Allows downloading an Excel file with results and saving to PostgreSQL (optional).

## Tech Stack

- **Backend**: FastAPI, Uvicorn
- **Orchestration**: LangGraph (StateGraph + MemorySaver)
- **LLM**: OpenAI (gpt-4o-mini by default)
- **PDF**: PyMuPDF (fitz), pdfplumber, PyPDF2
- **Data/Validation**: Pydantic, pydantic-settings
- **DB**: asyncpg (PostgreSQL) – optional
- **Excel**: openpyxl
- **Frontend**: Vanilla HTML/CSS/JS
- **Container**: Docker (multi-stage)

## Architecture and Pipeline Flow

File: `pipeline.py` (LangGraph)

Sequential node flow:
1) document_ingestion → 2) text_extraction → 3) text_cleaning → 4) llm → END

### Nodes (folder `nodes/`):

- **Node 1 – Ingestion** (`ingestion.py`)
  - Validates existence, size (<= settings.max_pdf_size_mb), PDF integrity, and extractable text.
  - Determines the most reliable extraction method (PyMuPDF/pdfplumber/PyPDF2) and stores metadata in `logging.debug_info`.

- **Node 2 – Extraction** (`extraction.py`)
  - Extracts text from up to 3 pages with the validated method.
  - Saves raw text in `state.text_content.raw_text` and statistics.

- **Node 3 – Cleaning** (`cleaning.py`)
  - Normalizes uppercase and spaces; calculates cleaning metrics.
  - Saves cleaned text in `state.text_content.cleaned_text`.

- **Node 4 – LLM** (`llm.py`)
  - Generates prompts (`models/prompts.py`) and calls OpenAI.
  - Parses JSON and stores in `state.extracted_data`. Updates metrics and marks `status=COMPLETED`.

## Pipeline State

Main model: `models/state.py` (Pydantic)

- **document_info**: file_path, filename, file_size
- **text_content**: raw_text, cleaned_text
- **processing_control**: processing_stage, status (PROCESSING/COMPLETED/FAILED)
- **metrics**: tokens_used, processing_time, cost_estimate, llm_model
- **quality**: confidence_score, completeness_score
- **logging**: messages, errors, warnings, debug_info
- **extracted_data**: dict with LLM result (customer, items, totals, withholding)

### Configuration: `models/settings.py`

- Reads `.env`. Required variables: `OPENAI_API_KEY` and `DATABASE_URL` (if using DB).
- Others: `llm_model`, `llm_temperature`, PDF limits, etc.

## API (FastAPI)

File: `main.py`

- **POST /upload**: Upload PDF. Returns `job_id` and initial status. Processing runs in background.
- **GET /status/{job_id}**: Job status (PENDING/PROCESSING/COMPLETED/FAILED).
- **GET /result/{job_id}**: Complete result when COMPLETED.
- **POST /guardar-factura**: Saves invoice to PostgreSQL from frontend data. Requires DB.
- **POST /guardar-factura-excel**: Generates and downloads Excel with submitted data.
- **GET /facturas**: Lists saved invoices (paginated). Requires DB.

### Notes:
- App can start without DB; save/list endpoints will return 503 if no connection.
- Dockerfile defines healthcheck to `/health`; add that endpoint or adjust healthcheck.

## Lightweight Frontend

Path: `frontend/`

- **`index.html`**: Interface with drag-and-drop or PDF selection, progress bar, and editable form.
- **`script.js`**: Calls API (`/upload`, `/status`, `/result`) and populates form with `extracted_data`. Allows Excel download via `/guardar-factura-excel`.
- **`styles.css`**: Modern and responsive styles.

**Usage**: Open `frontend/index.html` in browser with backend running at `http://localhost:8000` (CORS enabled for dev).

## Requirements and Configuration

### Prerequisites:
- Python 3.11+
- OpenAI API key (format `sk-...`)
- PostgreSQL (optional, for persistence)

### Minimum `.env` file in root:
```env
OPENAI_API_KEY=sk-XXXX
DATABASE_URL=postgresql://user:pass@host:5432/dbname  # optional if not using DB
TEMP_DIR=./temp
LLM_MODEL=gpt-4o-mini
```

## Local Execution (Windows PowerShell)

Install dependencies and start API:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open frontend:
- Double-click `frontend/index.html` or serve with a static server.

## Docker

Build and run:
```powershell
docker build -t invoice-processing:latest .
docker run -e OPENAI_API_KEY=sk-XXXX -e DATABASE_URL=postgresql://user:pass@host:5432/dbname -p 8000:8000 invoice-processing:latest
```

## Folder Structure (Summary)

```
.
├── main.py                # FastAPI API
├── pipeline.py            # LangGraph orchestration
├── database.py            # Async PostgreSQL manager (optional)
├── models/                # State, settings, prompts
├── nodes/                 # Nodes: ingestion, extraction, cleaning, llm
├── utils/                 # PDF, LLM, Excel, API helpers
├── frontend/              # Simple UI (HTML/JS/CSS)
├── requirements.txt       # Dependencies
├── Dockerfile             # Deployment image
└── temp/                  # Temporary files
```

## Notes and Limitations

- Up to 3 pages per PDF are processed in current extraction (adjustable).
- LLM responds only with JSON; if PDF has no extractable text, job fails with clear message.
- For persistence, assumes schema with `facturas` and `factura_items` tables (create before using `guardar-factura`).

## Use Cases

- **Accounting automation**: Extract invoice data for accounting systems
- **ERP integration**: Feed invoice data into ERP/CRM systems
- **Document digitization**: Convert paper invoices to structured data
- **Compliance**: Automated tax withholding calculation (Peruvian context)
- **Audit trails**: Track and store invoice history in database

## API Examples

### Upload Invoice
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@invoice.pdf"
```

Response:
```json
{
  "job_id": "abc123",
  "status": "PENDING",
  "message": "Invoice uploaded successfully"
}
```

### Check Status
```bash
curl "http://localhost:8000/status/abc123"
```

### Get Results
```bash
curl "http://localhost:8000/result/abc123"
```

Response:
```json
{
  "status": "COMPLETED",
  "extracted_data": {
    "customer": {
      "ruc": "20123456789",
      "name": "ACME Corp",
      "address": "Av. Example 123"
    },
    "items": [
      {
        "description": "Product A",
        "quantity": 10,
        "unit_price": 100.00,
        "total": 1000.00
      }
    ],
    "payment": {
      "method": "Credit",
      "currency": "PEN"
    },
    "totals": {
      "subtotal": 1000.00,
      "igv": 180.00,
      "total": 1180.00,
      "detraccion": 59.00
    }
  },
  "metrics": {
    "tokens_used": 1500,
    "processing_time": 3.5,
    "cost_estimate": 0.002
  }
}
```

## Troubleshooting

### Error: "No extractable text found"
- PDF is image-based (scanned). Solution: Add OCR support (Tesseract) or use vision-capable LLM.

### Error: OpenAI "insufficient_quota"
- No credits in OpenAI account. Solution: Add credits or use alternative provider.

### Error: Database connection failed
- PostgreSQL not running or wrong credentials. Solution: Check `DATABASE_URL` or run without DB (remove DB endpoints).

### PDF too large
- Exceeds 10 MB limit. Solution: Increase `MAX_PDF_SIZE_MB` in settings or compress PDF.

## Future Enhancements

- [ ] OCR support for scanned documents
- [ ] Multi-language support beyond Spanish
- [ ] Batch processing for multiple invoices
- [ ] Alternative LLM providers (Anthropic, local models)
- [ ] Invoice template recognition
- [ ] Duplicate invoice detection
- [ ] Integration with accounting software APIs

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This is a personal learning project. Free to use for educational purposes.

## Author

**Leon Achata**
- GitHub: [@LeonAchata](https://github.com/LeonAchata)

---

**Happy coding! 🚀**

*AI-Powered Invoice Processing with LangGraph - Production Ready*
