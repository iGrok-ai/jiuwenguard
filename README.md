# JiuwenGuard: Budget-Aware Agentic Harness

## Описание
Решение для соревнования openJiuwen Challenge 2026 (TECH ARENA 2026).
Харнесс анализирует 100 задач, оценивает стоимость в токенах, распознаёт невыполнимые задачи, сортирует оставшиеся по эффективности (reward/estimated_cost) и решает их через bash-исполнение со строгим контролем бюджета.

## Ключевые особенности
1. **Экономия токенов**: По умолчанию используется модель qwen3.8-27b-noreason, так как токены рассуждений считаются как выходные.
2. **Умная сортировка**: Задачи решаются в порядке убывания коэффициента reward / estimated_cost.
3. **Распознавание невыполнимых**: Задачи с подозрительно высокой оценкой стоимости (>1000) и низким reward (<5) отодвигаются в конец очереди или пропускаются.
4. **Защита от циклов**: Жёсткий лимит 8 шагов на задачу + таймаут 30 секунд на выполнение bash-команды.
5. **Точный учёт бюджета**: Формула (prompt_tokens / 10) + completion_tokens строго по регламенту. Кеш провайдера не вычитается.

## Структура репозитория
- run_agent.py — основной скрипт харнесса.
- Dockerfile — инструкция для сборки изолированного образа.
- requirements.txt — зависимости (openai).
- test_tasks/ — примеры задач для локального тестирования.

## Как запустить локально
```bash
export LLM_BASE_URL=https://api.neuraldeep.ru/v1
export LLM_API_KEY=your_api_key
python3 run_agent.py --tasks-dir ./test_tasks
```

## Как запускает жюри (Docker)
```bash
docker build -t hack:latest .
export TASKS=$(pwd)/test_tasks
export OUT=$(pwd)/out
mkdir -p "$OUT" && chmod 777 "$OUT"
docker run --rm --name run-test   -e LLM_BASE_URL -e LLM_API_KEY   -v "$TASKS:/data/tasks:rw"   --read-only --tmpfs /tmp:rw,size=2g -e HOME=/tmp   --cpus 8 --memory 16g --pids-limit 512   --workdir /app --entrypoint python   hack:latest /app/run_agent.py --tasks-dir /data/tasks
```

## Оценка расхода и поиск невыполнимых задач
- **Прогноз до запуска**: (длина_инструкции * 0.3 / 10) + 300 выходных токенов.
- **Фактический расход**: (prompt_tokens / 10) + completion_tokens.
- **Эвристика отсева**: Если estimated_cost > 1000 и reward < 5, задача считается подозрительной. Если агент превысил 8 шагов или bash вернул ошибку, задача прерывается для сохранения бюджета.

## Авторы
Команда JiuwenGuard — openJiuwen Challenge 2026
