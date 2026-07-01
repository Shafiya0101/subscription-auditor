FROM python:3.11-slim

# HuggingFace Spaces runs the container as UID 1000 — create that user to avoid
# permission issues (recommended by the Spaces Docker docs).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    METRICS_LOG=/home/user/app/metrics.jsonl

WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
