from app.llm.openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    name = "OpenRouter"
    base_url = "https://openrouter.ai/api/v1/chat/completions"
