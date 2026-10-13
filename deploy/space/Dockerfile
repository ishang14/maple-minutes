# MapleMinutes API for a Hugging Face Space (Docker SDK). Also runs anywhere Docker runs.
#
# The search index is baked into the image (data/qdrant) and the embedding model is downloaded at build
# time, so a sleeping Space wakes up without downloading anything: it only has to load the index into memory.
FROM python:3.12-slim

# Hugging Face runs the container as user 1000, so build and run as that user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    FASTEMBED_CACHE_PATH=/home/user/models
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install -r requirements.txt

# Download the query-embedding model now (it must match EMBEDDING_MODEL and the model the index was built with).
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

COPY --chown=user app ./app
COPY --chown=user data ./data

# Deployment defaults. Secrets and the frontend address are NOT set here: add GROQ_API_KEY as a Space secret and
# ALLOWED_ORIGINS (your frontend URL) as a Space variable.
#  - dense search with no reranker: the evaluation found it as accurate as hybrid and 10 to 18 times faster
#  - the visitor's address comes from X-Forwarded-For, which Hugging Face's proxy sets
ENV SEARCH_MODE=dense \
    RERANK_ENABLED=false \
    TRUST_PROXY_HEADERS=true \
    EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    QDRANT_PATH=/home/user/app/data/qdrant \
    LLM_PROVIDER=groq

EXPOSE 7860

# One worker only: the on-disk index can be opened by a single process at a time.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
