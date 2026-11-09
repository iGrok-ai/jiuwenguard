FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем основной скрипт
COPY run_agent.py .

# Переменные окружения по умолчанию (будут перезаписаны при запуске жюри)
ENV LLM_BASE_URL="http://localhost:8000/v1"
ENV LLM_API_KEY="dummy-key"
ENV BUDGET_LIMIT="50000"

# CMD используется, так как жюри перезаписывает ENTRYPOINT через --entrypoint python
CMD ["python", "/app/run_agent.py", "--tasks-dir", "/data/tasks"]
