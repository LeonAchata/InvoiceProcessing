from models.state import PipelineState

# ================================
# PROMPT PRINCIPAL - EXTRACCIÓN COMPLETA
# ================================

EXTRACTION_SYSTEM_PROMPT = """Eres un experto contador que se especializa en extraer datos de facturas peruanas.
Tu tarea es analizar el texto de facturas y extraer datos específicos en formato JSON válido.
Responde ÚNICAMENTE con JSON, sin markdown, sin explicaciones adicionales."""

EXTRACTION_USER_PROMPT = """Analiza el siguiente texto de factura peruana y extrae los datos en formato JSON.

REGLAS ESTRICTAS:
1. Extrae SOLO información explícitamente presente en el texto.
2. NO inventes, infieras ni reformatees datos.
3. Si un campo no existe: usa null.
4. Si hay ambigüedad: usa el valor más específico y exacto.
5. Todos los montos deben tener hasta 2 decimales (ej: 1500.00).
6. Todos los strings deben conservar el texto tal cual aparece, excepto donde se indique lo contrario.
7. NO incluyas ningún comentario ni texto adicional: responde ÚNICAMENTE con JSON válido.

ESTRUCTURA DEL JSON A RETORNAR:

- codigo_cliente: RUC (11 dígitos) o DNI (8 dígitos) del CLIENTE. String o null.
- razon_social_cliente: Nombre o razón social EXACTO del cliente, según figura en la factura. String o null.
- direccion_cliente: Dirección completa del cliente (SIN distrito ni departamento). MAYÚSCULAS, sin comas ni paréntesis. String o null.
- distrito: Distrito peruano del cliente en MAYÚSCULAS. String o null.
- items: Array de objetos con cada producto o servicio. Cada objeto debe tener:
  - descripcion: String
  - cantidad: Number
  - precio_unitario: Number
  - subtotal: Number
- forma_pago: Condición de pago (CONTADO/CREDITO/TARJETA/EFECTIVO/TRANSFERENCIA/YAPE/PLIN). String o null.
- moneda: Código ISO (PEN para soles, USD para dólares). String o null.
- subtotal: Subtotal antes de impuestos. Number o null.
- igv: Monto de IGV (18%). Number o null.
- total: Importe total a pagar. Number o null.
- detraccion: Objeto con los campos:
  - porcentaje: Number
  - monto: Number
  Solo si la detracción está explícitamente indicada. En caso contrario: null.

FORMATO DE EJEMPLO:
{
  "codigo_cliente": "20123456789",
  "razon_social_cliente": "EMPRESA COMERCIAL SAC",
  "direccion_cliente": "AV LOS CONQUISTADORES 456",
  "distrito": "SAN ISIDRO",
  "items": [
    {
      "descripcion": "SERVICIO DE CONSULTORIA",
      "cantidad": 1.00,
      "precio_unitario": 1500.00,
      "subtotal": 1500.00
    }
  ],
  "forma_pago": "CREDITO",
  "moneda": "PEN",
  "subtotal": 1500.00,
  "igv": 270.00,
  "total": 1770.00,
  "detraccion": {
    "porcentaje": 12.00,
    "monto": 177.00
  }
}

TEXTO DE LA FACTURA:
---
{cleaned_text}
---

Responde únicamente con el JSON:
"""

# ================================
# FUNCIÓN GENERADORA DE PROMPTS
# ================================
def generate_extraction_prompts(text) -> tuple[str,str]:
    """
    Genera los prompts para extracción usando el estado actual.
    
    Args:
        state: Estado del pipeline con el texto limpio
        
    Returns:
        tuple: (system_prompt, user_prompt)
    """
    system_prompt = EXTRACTION_SYSTEM_PROMPT
    
    # Verificar que el texto esté disponible
    if not text:
        raise ValueError("No hay texto limpio disponible en el estado")
    
    user_prompt = EXTRACTION_USER_PROMPT.format(
        cleaned_text=text
    )

    return system_prompt, user_prompt