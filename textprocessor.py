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
        model: str = "ai/granite-4.0-micro",
        base_url: Optional[str] = None
    ):
        """
        Initialize the TextProcessor with Docker Model Runner or OpenAI API.
        
        Args:
            api_key: API key (if None, reads from OPENAI_API_KEY env var, or "not-needed" for local)
            model: Model to use for summarization (default: docker.io/granite-4.0-nano:350M-BF16)
            base_url: Base URL for the API (default: http://localhost:8080/v1 for Docker Model Runner)
        """
        # For Docker Model Runner, API key is not required but OpenAI client needs something
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or "not-needed"
        
        # Default to Docker Model Runner URL if not specified
        self.base_url = base_url or os.getenv("MODEL_RUNNER_URL", "http://localhost:12434/v1")
        
        # Initialize OpenAI client with custom base URL for Docker Model Runner
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.model = model
    
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
                model=self.model,
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
                model=self.model,
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
                model=self.model,
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
    

    # Case detauls 
    def extract_case_details(self, text: str) -> Dict[str, Any]:
        """Extracts specific legal/dispute fields for the XGBoost model."""
        system_prompt = (
            "You are a legal data extractor. Extract the following fields from the text "
            "and return ONLY a valid JSON object. Fields: case_id, claim_amount, delay_days, "
            "document_count, dispute_type, jurisdiction, probability (Low/Medium/High), "
            "document_score (0-10), settle_min, settle_max."
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model, # Using micro as requested
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content)
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
            model=self.model,
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
    model: str = "docker.io/granite-4.0-nano:350M-BF16",
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
