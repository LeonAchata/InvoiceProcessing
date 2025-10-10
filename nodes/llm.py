import logging
import json
from openai import OpenAI
from models.settings import settings
from models.state import PipelineState
from models.prompts import generate_extraction_prompts

def llm_node(state: PipelineState) -> PipelineState:
    logger = logging.getLogger("Nodo 6")
    state = state.update_stage("llm_processing")

    try:
        client = OpenAI(api_key=settings.openai_api_key)
    except Exception as e:
        return state.add_error(f"Error inicializando cliente OpenAI: {str(e)}")
    
    try:
        cleaned_text = state.text_content.cleaned_text
        system_prompt, user_prompt = generate_extraction_prompts(cleaned_text)

        print("=== SYSTEM PROMPT ===")
        print(system_prompt)
        print("\n=== USER PROMPT ===")
        print(user_prompt[:500] + "...")

        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500,
            temperature=settings.llm_temperature,
            top_p=0.9
        )

        tokens_used = response.usage.total_tokens if response.usage else 0
        content = response.choices[0].message.content.strip()

        print("\n=== RAW RESPONSE ===")
        print(content[:300])

        # Limpiar formato JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()
        print("\n=== CLEANED CONTENT ===")
        print(content[:300])

        result = json.loads(content)

        if not isinstance(result, dict):
            raise ValueError("Respuesta de OpenAI no es un objeto JSON válido")

        state.extracted_data = result
        state.update_metrics(tokens=tokens_used)
        state.processing_control.status = "COMPLETED"
        
        logger.info(f"Extracción exitosa: {len(result)} campos, {tokens_used} tokens")
        return state.add_message(f"Extracción completada: {len(result)} campos extraídos")
        
    except Exception as e:
        logger.error(f"Error en extracción LLM: {str(e)}")
        return state.add_error(f"Error en extracción LLM: {str(e)}")