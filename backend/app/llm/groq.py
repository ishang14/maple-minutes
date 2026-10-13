from app.llm.openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    name = "Groq"
    base_url = "https://api.groq.com/openai/v1/chat/completions"
