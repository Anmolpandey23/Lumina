"""
LLM client for answer generation
Supports OpenAI and local models via llamacpp, ollama, etc.
"""

import os
import logging
from typing import Optional, Dict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base for LLM providers"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate answer based on context"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT models"""

    def __init__(self, model: str = "gpt-3.5-turbo", api_key: Optional[str] = None):
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
            self.model = model
            logger.info(f"Initialized OpenAI provider: {model}")
        except ImportError:
            raise ImportError("Install openai: pip install openai")

    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate answer using OpenAI API"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that answers questions based on provided context. Always cite the source and be concise."
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {prompt}"
                }
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider"""

    def __init__(self, model: str = "mistral", base_url: str = "http://localhost:11434"):
        try:
            import requests
            self.model = model
            self.base_url = base_url
            self.requests = requests
            logger.info(f"Initialized Ollama provider: {model} at {base_url}")
        except ImportError:
            raise ImportError("Install requests: pip install requests")

    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate answer using Ollama"""
        try:
            full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}\n\nAnswer:"

            response = self.requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": temperature,
                },
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("response", "No response")
            else:
                raise Exception(f"Ollama returned {response.status_code}")

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise


class GeminiProvider(LLMProvider):
    """Google Gemini models (FREE tier available)"""

    def __init__(self, model: str = "gemini-pro-latest", api_key: Optional[str] = None):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key or os.getenv("GEMINI_API_KEY"))
            self.model = genai.GenerativeModel(model)
            self.model_name = model
            logger.info(f"Initialized Gemini provider: {model}")
        except ImportError:
            raise ImportError("Install google-generativeai: pip install google-generativeai")

    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate answer using Gemini API"""
        try:
            full_prompt = f"""You are a helpful assistant that answers questions based on provided context.

Context:
{context}

Question: {prompt}

Provide a clear, concise answer based on the context above."""

            response = self.model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise


class HuggingFaceProvider(LLMProvider):
    """Hugging Face Inference API provider"""

    def __init__(
        self,
        model: str = "meta-llama/Llama-3.1-8B-Instruct",
        api_key: Optional[str] = None,
        base_url: str = "https://router.huggingface.co/v1/chat/completions"
    ):
        try:
            import requests
            self.requests = requests
            self.model = model
            self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY")
            self.base_url = base_url.rstrip("/")

            logger.info(f"Initialized Hugging Face provider: {model}")
        except ImportError:
            raise ImportError("Install requests: pip install requests")

    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate answer using Hugging Face Inference API"""
        try:
            if not self.api_key:
                raise Exception("HUGGINGFACE_API_KEY is missing for Hugging Face provider")

            full_prompt = (
                "You are a helpful assistant that answers questions based on provided context. "
                "Rules: (1) Answer the CURRENT user question directly. "
                "(2) Prefer page context and source snippets over conversation recap. "
                "(3) Do not start with phrases like 'Based on recent conversation history' unless explicitly asked. "
                "(4) If UI cues provide a count (for example notifications), return the number directly. "
                "(5) If information is missing, say exactly what is missing in one sentence. "
                "Be concise and grounded in the context.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {prompt}"
            )

            response = self.requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": full_prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=60,
            )

            if response.status_code >= 400:
                # Truncate response body: some providers echo the API key in 401/403 error messages
                safe_body = (response.text or "")[:300]
                raise Exception(f"Hugging Face API error {response.status_code}: {safe_body}")

            data = response.json()

            if isinstance(data, dict):
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    generated = (message.get("content") or "").strip()
                    if generated:
                        return generated

            raise Exception(f"Unexpected Hugging Face response format: {data}")

        except Exception as e:
            logger.error(f"Hugging Face generation failed: {e}")
            raise


class MockLLMProvider(LLMProvider):
    """Mock provider for testing"""

    def generate(
        self,
        prompt: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Return mock response"""
        return f"[Mock Response to: {prompt}]\nBased on context about this topic, the answer is informative and helpful."


class LLMClient:
    """Client for LLM generation"""

    def __init__(
        self,
        provider_type: str = "mock",
        model: Optional[str] = None,
        **kwargs
    ):
        if provider_type == "openai":
            self.provider = OpenAIProvider(model or "gpt-3.5-turbo", **kwargs)
        elif provider_type == "ollama":
            self.provider = OllamaProvider(model or "mistral", **kwargs)
        elif provider_type == "gemini":
            self.provider = GeminiProvider(model or "gemini-pro-latest", **kwargs)
        elif provider_type == "huggingface":
            self.provider = HuggingFaceProvider(model or "meta-llama/Llama-3.1-8B-Instruct", **kwargs)
        elif provider_type == "mock":
            self.provider = MockLLMProvider()
        else:
            raise ValueError(f"Unknown provider: {provider_type}")

        self.provider_type = provider_type

    def generate_answer(
        self,
        query: str,
        context: str,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> Dict:
        """
        Generate answer for query given context
        
        Args:
            query: User query
            context: Retrieved context from RAG
            max_tokens: Max tokens in response
            temperature: Temperature for generation
            
        Returns:
            Dict with answer and metadata
        """
        try:
            answer = self.provider.generate(
                query, context, max_tokens, temperature
            )

            return {
                "success": True,
                "answer": answer,
                "provider": self.provider_type,
                "tokens_used": len(answer.split())  # Rough estimate
            }

        except Exception as e:
            error_text = str(e)
            logger.error(f"Answer generation failed: {error_text}")

            lower_error = error_text.lower()
            if "api_key_invalid" in lower_error or "api key not valid" in lower_error:
                user_message = "Gemini API key is invalid. Please regenerate the key in Google AI Studio and update backend/.env."
            elif "quota" in lower_error or "429" in lower_error or "rate limit" in lower_error or "resource_exhausted" in lower_error:
                user_message = "Gemini free quota is currently exhausted. Please wait a bit and retry, or use another Gemini key/project with available quota."
            elif "huggingface_api_key" in lower_error or "huggingface_api_key is missing" in lower_error:
                user_message = "Hugging Face API key is missing. Add HUGGINGFACE_API_KEY in backend/.env."
            elif "401" in lower_error and ("hugging face" in lower_error or "huggingface" in lower_error):
                user_message = "Hugging Face API key is invalid. Generate a new token and update backend/.env."
            elif "hugging face" in lower_error or "huggingface" in lower_error:
                user_message = "Hugging Face API request failed. Check HUGGINGFACE_API_KEY, selected model, and current free-tier limits."
            elif "not found" in lower_error and "model" in lower_error:
                user_message = "Configured model is not available for this provider. Update LLM_MODEL to a supported model name."
            else:
                user_message = "Sorry, I couldn't generate an answer. Please try again."

            return {
                "success": False,
                "answer": user_message,
                "error": error_text,
                "provider": self.provider_type
            }
