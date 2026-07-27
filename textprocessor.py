import os
from typing import Optional, Dict, Any
from openai import OpenAI
import json

class TextProcessor:
    """
    Text processor that uses Docker Model Runner (or OpenAI API) to generate summaries
    of processed text content.
    
    Supports Docker Model Runner with OpenAI-compatible API for local mo
    dels.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the TextProcessor with Docker Model Runner or OpenAI API.
        
        Three model slots, each configurable via .env:
          MODEL_FOR_CHAT      – conversational chat (default: ai/granite-4.0-h-micro)
          MODEL_FOR_ANALYSIS  – extraction + reasoning (default: ai/granite-4.0-h-micro)
          MODEL_FOR_SUMMARIZE – fast summarization (default: ai/granite-4.0-h-nano)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or "not-needed"
        self.base_url = base_url or os.getenv("BASE_URL", "http://localhost:12434/v1")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        # If caller passes an explicit model, use it everywhere (backward compat)
        # Otherwise read per-task env vars
        _default_analysis  = os.getenv("MODEL_FOR_ANALYSIS",  "ai/granite-4.0-h-micro")
        _default_chat      = os.getenv("MODEL_FOR_CHAT",      "ai/granite-4.0-h-micro")
        _default_summarize = os.getenv("MODEL_FOR_SUMMARIZE", "ai/granite-4.0-h-nano")

        self.model          = model or _default_chat      # legacy fallback
        self.chat_model     = model or _default_chat
        self.analysis_model = model or _default_analysis  # used for extraction & reasoning
        self.summarize_model= model or _default_summarize # used for summarize/key-points

    
    def summarize(
        self,
        text: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a summary of the provided text using OpenAI API.
        
        Args:
            text: The text content to summarize
            max_tokens: Maximum tokens in the summary response
            temperature: Sampling temperature (0-2). Higher = more random
            custom_prompt: Optional custom system prompt for summarization
            
        Returns:
            Dict containing:
                - summary: The generated summary text
                - model: Model used
                - tokens_used: Token usage information
        """
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")
        
        # Default system prompt for summarization
        system_prompt = custom_prompt or (
            "You are a professional summarization assistant. "
            "Provide clear, concise, and accurate summaries of the given text. "
            "Capture the key points, main ideas, and important details."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.summarize_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Please summarize the following text:\n\n{text}"}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return {
                "summary": response.choices[0].message.content,
                "model": response.model,
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                },
                "finish_reason": response.choices[0].finish_reason
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate summary: {str(e)}")
    
    def extract_key_points(
        self,
        text: str,
        num_points: int = 5,
        max_tokens: int = 300
    ) -> Dict[str, Any]:
        """
        Extract key points from the text.
        
        Args:
            text: The text content to analyze
            num_points: Number of key points to extract
            max_tokens: Maximum tokens in the response
            
        Returns:
            Dict containing key points and metadata
        """
        system_prompt = (
            f"Extract the {num_points} most important key points from the text. "
            "Return them as a numbered list. Be concise and specific."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.summarize_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=max_tokens,
                temperature=0.5
            )
            
            return {
                "key_points": response.choices[0].message.content,
                "model": response.model,
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to extract key points: {str(e)}")
    
    def custom_analysis(
        self,
        text: str,
        instruction: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Perform custom text analysis based on user instruction.
        
        Args:
            text: The text content to analyze
            instruction: Custom instruction for the analysis
            max_tokens: Maximum tokens in the response
            temperature: Sampling temperature
            
        Returns:
            Dict containing analysis results and metadata
        """
        try:
            response = self.client.chat.completions.create(
                model=self.analysis_model,
                messages=[
                    {"role": "system", "content": "You are a helpful text analysis assistant."},
                    {"role": "user", "content": f"{instruction}\n\nText:\n{text}"}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return {
                "result": response.choices[0].message.content,
                "model": response.model,
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to perform custom analysis: {str(e)}")
    

    def _parse_json_response(self, content: str) -> Dict:
        """Robustly parse JSON from LLM output, handling markdown code fences."""
        import re
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        match = re.search(r'```(?:json)?\s*([\s\S]+?)```', content)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Try to find first { ... } block
        match = re.search(r'(\{[\s\S]+\})', content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from model response: {content[:300]}")

    # Case details
    def extract_case_details(self, text: str) -> Dict[str, Any]:
        """Extracts specific legal/dispute fields for the XGBoost model."""
        system_prompt = (
            "Role: You are a high-precision Legal & Financial Data Extractor for Indian MSME dispute cases."
            "Task: Extract required fields from the input text and return ONLY a valid JSON object."
            "\n"
            "FIELD EXTRACTION RULES:\n"
            "\n"
            "claim_amount (integer, no commas/symbols):\n"
            "  - If an explicit disputed/claimed amount is stated, use it directly.\n"
            "  - SLA credit disputes: credit = (credit_percentage / 100) * total_invoice_amount. NEVER multiply by hours or days.\n"
            "    Example: 15% credit on ₹1,12,100 = 0.15 * 112100 = 16815. NOT 9 * 0.15 * 112100.\n"
            "  - Late delivery penalty: penalty = (penalty_pct / 100) * invoice_amount, capped at stated maximum.\n"
            "  - Payment disputes: use the unpaid invoice total.\n"
            "\n"
            "delay_days (integer):\n"
            "  - For payment delays: extract the number of days overdue from due date to filing date.\n"
            "  - For outages/downtime: convert hours to days by dividing by 24 and ROUNDING UP. Example: 9 hours = ceil(9/24) = 1 day.\n"
            "  - For delivery delays: count calendar days between contractual and actual delivery date.\n"
            "\n"
            "dispute_type (must be exactly one of these values):\n"
            "  - 'others': SLA breaches, uptime credits, quality disputes, service level failures\n"
            "  - 'service_non_payment': services rendered and accepted but invoice not paid\n"
            "  - 'invoice_non_payment': goods delivered but invoice not paid\n"
            "  - 'goods_rejection': buyer rejected delivered goods\n"
            "  - 'short_payment': payment received but less than invoiced amount\n"
            "  - 'interest_on_delay': claim is specifically for interest on delayed payment\n"
            "  NOTE: SLA downtime credit claims = 'others', NOT 'service_non_payment'\n"
            "\n"
            "document_count (integer): Count every distinct evidence item (Invoice, SLA doc, Incident Report, Email, PO, MOU, etc.)\n"
            "jurisdiction (string): Extract the Indian State name in Title Case from city/office locations.\n"
            "document_score (integer 0-10): Rate completeness of evidence provided.\n"
            "clarify (string): One sentence showing your exact calculation with numbers.\n"
            "confidence_level (integer 0-10): Your confidence in the extraction.\n"
            "\n"
            "Constraint: Return ONLY the JSON object. No markdown, no extra text."
        )

        validator_prompt = (
            "Role: You are a Strict Data Auditor validating extracted legal case fields.\n"
            "\n"
            "VALIDATION RULES — check each field:\n"
            "\n"
            "claim_amount:\n"
            "  - SLA credit = (pct/100) * total_invoice. NEVER multiply by hours. Example: 15% of 112100 = 16815.\n"
            "  - Verify the clarify field shows correct arithmetic. If wrong, recalculate and correct.\n"
            "\n"
            "delay_days:\n"
            "  - Hours → days: ceil(hours / 24). Example: 9 hours → ceil(0.375) = 1 day. NOT 9.\n"
            "  - Verify this conversion was done correctly.\n"
            "\n"
            "dispute_type:\n"
            "  - SLA / uptime / downtime credit = 'others'\n"
            "  - Must be exactly one of: goods_rejection, service_non_payment, invoice_non_payment, short_payment, interest_on_delay, others\n"
            "\n"
            "jurisdiction: Must be a real Indian State name.\n"
            "\n"
            "Output: Return a corrected JSON with all validated/corrected values plus is_passed (true/false).\n"
            "Constraint: Return ONLY the JSON object. No markdown, no extra text."
        )


        try:
            response = self.client.chat.completions.create(
                model=self.analysis_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
            )
            raw_response = response.choices[0].message.content
            print("response", raw_response)
            extracted = self._parse_json_response(raw_response)

            validate = self.client.chat.completions.create(
                model=self.analysis_model,
                messages=[
                    {"role": "system", "content": validator_prompt},
                    {"role": "user", "content": f"Source Text:\n{text}\n\nExtracted JSON:\n{raw_response}"}
                ],
                temperature=0.1,
            )
            raw_validate = validate.choices[0].message.content
            print("validate", raw_validate)
            try:
                validated = self._parse_json_response(raw_validate)
                # If validator says passed, use its output; else fall back to first extraction
                return validated if validated.get("is_passed") else extracted
            except Exception:
                # Validator parse failed — still return the good first extraction
                return extracted

        except Exception as e:
            raise RuntimeError(f"Extraction failed: {str(e)}")

        
    def draft_settlement(self, text: str, outcome_data: Dict) -> str:
        """Drafts a settlement based on document text and XGBoost predictions."""
        prompt = f"""
        Based on the following document text and the predicted outcome data, draft a 
        professional settlement proposal. Include specific clauses and reference 
        the probability rate.
        
        Outcome Data: {json.dumps(outcome_data)}
        """
        response = self.client.chat.completions.create(
            model=self.analysis_model,
            messages=[
                {"role": "system", "content": "You are a senior legal counsel drafting a settlement agreement."},
                {"role": "user", "content": f"{prompt}\n\nDocument Text:\n{text}"}
            ]
        )
        return response.choices[0].message.content
# Convenience function for quick summarization
def quick_summarize(
    text: str, 
    api_key: Optional[str] = None,
    model: str = None,
    base_url: Optional[str] = None
) -> str:
    """
    Quick function to summarize text without instantiating a class.
    
    Args:
        text: Text to summarize
        api_key: Optional API key
        model: Model to use
        base_url: Optional base URL for API
        
    Returns:
        Summary text string
    """
    processor = TextProcessor(api_key=api_key, model=model, base_url=base_url)
    result = processor.summarize(text)
    return result["summary"]
