FROM python:3.11.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run_agent.py .

ENV LLM_BASE_URL="http://localhost:8000/v1"
ENV LLM_API_KEY="dummy-key"
ENV BUDGET_LIMIT="50000"

CMD ["python", "/app/run_agent.py", "--tasks-dir", "/data/tasks"]
