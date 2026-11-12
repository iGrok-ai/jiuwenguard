import os
import sys
import json
import subprocess
import re
import argparse
from openai import OpenAI

# Переменные окружения
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "dummy-key")
BUDGET_LIMIT = float(os.environ.get("BUDGET_LIMIT", 50000))
OUT_DIR = os.environ.get("OUT")

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

# Модели (Пункт 2: Умный выбор)
MODELS = {
    "fast": "qwen3.6-35b-a3b-noreason",      # Для коротких и простых
    "standard": "qwen3.8-27b-noreason",       # Базовая
    "smart": "qwen3.8-27b"                    # Для сложных (с рассуждением)
}

def clean_json_keys(data):
    return {k.strip(): v.strip() if isinstance(v, str) else v for k, v in data.items()}

def estimate_task_cost(instruction):
    return (len(instruction) * 0.3 / 10.0) + 300

def calculate_actual_cost(usage):
    prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
    completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
    # Токены рассуждений тоже считаем как выходные
    reasoning_tokens = getattr(usage, 'completion_tokens_details', {}).get('reasoning_tokens', 0) or 0
    return (prompt_tokens / 10.0) + completion_tokens + reasoning_tokens

def choose_model(instruction, reward):
    # Пункт 2: Выбор модели в зависимости от длины и награды
    if len(instruction) < 150 and reward <= 2:
        return MODELS["fast"]
    if len(instruction) > 400 or reward >= 4:
        return MODELS["smart"]
    return MODELS["standard"]

def is_unsolvable(instruction):
    # Пункт 3: Эвристика невыполнимых задач
    skip_words = ["impossible", "невозможно", "не существует", "unknown", "выдумай несуществующее"]
    if any(w in instruction.lower() for w in skip_words):
        return True
    return False

def solve_task(task_dir, task_data):
    instruction = task_data.get("instruction", "")
    reward = task_data.get("reward", 0)
    
    # Пункт 3: Сразу пропускаем явно невыполнимые
    if is_unsolvable(instruction):
        print(f"  [~] Task marked as unsolvable by heuristics. Skipped.")
        return False, 0.0

    model = choose_model(instruction, reward)
    
    system_prompt = (
        "You are an autonomous agent. Solve the task step by step.\n"
        "To execute a command, respond ONLY with:\n```bash\n<command>\n```\n"
        "When done, respond ONLY with:\n```answer\n<final answer>\n```\n"
        "Do not write anything else."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction}
    ]
    
    total_task_cost = 0.0
    max_steps = 8
    
    for step in range(max_steps):
        # Пункт 4: Управление контекстом (обрезаем историю, если слишком длинная)
        if len(messages) > 6:
            messages = [messages[0], messages[1]] + messages[-4:]
            
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=0.1, timeout=60
            )
        except Exception as e:
            print(f"  [!] API error: {e}")
            return False, total_task_cost
            
        content = response.choices[0].message.content
        step_cost = calculate_actual_cost(response.usage)
        total_task_cost += step_cost
        messages.append({"role": "assistant", "content": content})
        
        # Проверка ответа
        answer_match = re.search(r'```answer\s*(.*?)\s*```', content, re.IGNORECASE | re.DOTALL)
        if answer_match:
            raw_answer = answer_match.group(1).strip()
            final_answer = re.sub(r'[^\d-]', '', raw_answer)
            if not final_answer:
                nums = re.findall(r'\d+', raw_answer)
                if nums: final_answer = nums[0]
            
            with open(os.path.join(task_dir, "answer.txt"), "w") as f:
                f.write(final_answer + "\n")
            return True, total_task_cost
            
        # Проверка bash
        bash_match = re.search(r'```bash\s*(.*?)\s*```', content, re.IGNORECASE | re.DOTALL)
        if bash_match:
            command = bash_match.group(1).strip()
            try:
                res = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=task_dir, timeout=30)
                output = f"OUT:\n{res.stdout}\nERR:\n{res.stderr}\nRC: {res.returncode}"
            except Exception as e:
                output = f"ERROR: {str(e)}"
            messages.append({"role": "user", "content": f"Output:\n{output}"})
        else:
            messages.append({"role": "user", "content": "Provide bash command or ```answer```."})
            
    return False, total_task_cost

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", type=str, required=True)
    args = parser.parse_args()
    tasks_dir = args.tasks_dir
    
    print(f"Starting. Dir: {tasks_dir}, Budget: {BUDGET_LIMIT}")
    
    tasks = []
    for folder in os.listdir(tasks_dir):
        path = os.path.join(tasks_dir, folder)
        json_path = os.path.join(path, "task.json")
        if os.path.isdir(path) and os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = clean_json_keys(json.load(f))
                data["_dir"] = path
                data["_cost"] = estimate_task_cost(data.get("instruction", ""))
                tasks.append(data)
                
    # Сортировка по выгоде
    tasks.sort(key=lambda x: x.get("reward", 1) / max(x["_cost"], 1), reverse=True)
    
    total_spent = 0.0
    total_reward = 0
    results = []
    
    for task in tasks:
        if total_spent >= BUDGET_LIMIT:
            break
            
        # Пункт 3: Пропуск дорогих и дешевых
        if task["_cost"] > 1200 and task.get("reward", 0) < 4:
            continue
            
        print(f"Task: {task.get('task_id')} (R: {task.get('reward')}, Est: {task['_cost']:.1f})")
        success, cost = solve_task(task["_dir"], task)
        total_spent += cost
        
        if success:
            total_reward += task.get("reward", 0)
            results.append({"task_id": task.get("task_id"), "status": "solved"})
        else:
            results.append({"task_id": task.get("task_id"), "status": "failed"})
            
        print(f"Spent: {cost:.1f} | Total: {total_spent:.1f} / {BUDGET_LIMIT}")
        
    # Пункт 7: Сохранение общего отчета в OUT, если переменная задана
    if OUT_DIR and os.path.isdir(OUT_DIR):
        with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
            json.dump({"total_reward": total_reward, "total_spent": total_spent, "results": results}, f)
        print(f"Summary saved to {OUT_DIR}")
        
    print(f"\nDONE! Solved: {sum(1 for r in results if r['status']=='solved')}, Reward: {total_reward}, Cost: {total_spent:.1f}")

if __name__ == "__main__":
    main()
