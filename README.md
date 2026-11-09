# JiuwenGuard: Budget-Aware Agentic Harness

## Описание
Решение для соревнования openJiuwen Challenge 2026 (TECH ARENA 2026).

Харнесс анализирует 100 задач, оценивает стоимость в токенах, распознаёт невыполнимые, сортирует по эффективности и решает через bash с контролем бюджета.

## Ключевые особенности
1. Модель qwen3.8-27b-noreason для простых задач (экономит токены рассуждения)
2. Умная сортировка по reward/estimated_cost
3. Эвристики отсева невыполнимых задач
4. Лимит 8 шагов + таймаут 30 сек на bash
5. Формула учёта: (prompt_tokens / 10) + completion_tokens

## Структура
- run_agent.py - основной скрипт
- Dockerfile - сборка образа
- requirements.txt - зависимости

## Запуск локально
export LLM_BASE_URL=https://api.neuraldeep.ru/v1
export LLM_API_KEY=your_key
python3 run_agent.py --tasks-dir ./test_tasks

## Запуск через Docker
docker build -t hack:latest .
export TASKS=$(pwd)/test_tasks
export OUT=$(pwd)/out
mkdir -p $OUT && chmod 777 $OUT
docker run --rm -e LLM_BASE_URL -e LLM_API_KEY -v $TASKS:/data/tasks:rw --read-only --tmpfs /tmp:rw,size=2g -e HOME=/tmp --cpus 8 --memory 16g --workdir /app --entrypoint python hack:latest /app/run_agent.py --tasks-dir /data/tasks

## Оценка расхода
Прогноз: длина_инструкции * 0.3 / 10 + 300
Факт: (prompt_tokens / 10) + completion_tokens
Кеш не вычитается.

## Распознавание невыполнимых
- estimated_cost > 1000 и reward < 5 - подозрительно
- ratio reward/cost < 0.01 - в конец очереди
- Превышение 8 шагов - прерывание
- 3 ошибки bash подряд - невыполнима

## Авторы
Команда JiuwenGuard - openJiuwen Challenge 2026
