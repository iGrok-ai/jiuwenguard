import os
import sys
import json
import subprocess
import re
import argparse
from openai import OpenAI

MODEL_NAME = os.environ.get("MODEL_NAME", "qwen3.8-27b-noreason")
MAX_STEPS_PER_TASK = 8
BUDGET_LIMIT = float(os.environ.get("BUDGET_LIMIT", 50000))

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "http://localhost:8000/v1"),
    api_key=os.environ.get("LLM_API_KEY", "dummy-key")
)

def clean_json_keys(data):
    return {k.strip(): v.strip() if isinstance(v, str) else v for k, v in data.items()}

def estimate_task_cost(instruction):
    estimated_input_tokens = len(instruction) * 0.3
    estimated_output_tokens = 300
    return (estimated_input_tokens / 10.0) + estimated_output_tokens

def calculate_actual_cost(usage):
    prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
    completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
    return (prompt_tokens / 10.0) + completion_tokens

def solve_task(task_dir, task_data):
    instruction = task_data.get("instruction", "")
    
    system_prompt = (
        "You are an autonomous data analysis agent. Solve the task step by step.\n"
        "To execute a bash or python command, respond ONLY with a markdown code block:\n"
        "```bash\n<your command>\n```\n"
        "I will execute it in the current directory and return the output.\n"
        "When you know the final answer, respond ONLY with:\n"
        "```answer\n<your final answer>\n```\n"
        "Do not write anything else. Work only inside the current directory."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": instruction}
    ]
    
    total_task_cost = 0.0
    
    for step in range(MAX_STEPS_PER_TASK):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.1,
                timeout=60
            )
        except Exception as e:
            print(f"  [!] API error at step {step}: {e}")
            return False, 0.0
            
        content = response.choices[0].message.content
        usage = response.usage
        step_cost = calculate_actual_cost(usage)
        total_task_cost += step_cost
        messages.append({"role": "assistant", "content": content})
        
        answer_match = re.search(r'```answer\s*(.*?)\s*```', content, re.IGNORECASE | re.DOTALL)
        if answer_match:
            raw_answer = answer_match.group(1).strip()
            # Оставляем ТОЛЬКО цифры и знак минуса (убирает %, буквы, пробелы)
            final_answer = re.sub(r'[^\d-]', '', raw_answer)
            if not final_answer:
                numbers = re.findall(r'\d+', raw_answer)
                if numbers:
                    final_answer = numbers[0]
            
            answer_file = os.path.join(task_dir, "answer.txt")
            with open(answer_file, "w", encoding="utf-8") as f:
                f.write(final_answer + "\n")
            print(f"  [+] Task solved! Answer saved: {final_answer}. Cost: {total_task_cost:.1f}")
            return True, total_task_cost
            
        bash_match = re.search(r'```bash\s*(.*?)\s*```', content, re.IGNORECASE | re.DOTALL)
        if bash_match:
            command = bash_match.group(1).strip()
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=task_dir,
                    timeout=30
                )
                output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nRETURN CODE: {result.returncode}"
            except subprocess.TimeoutExpired:
                output = "EXECUTION ERROR: Command timed out after 30 seconds."
            except Exception as e:
                output = f"EXECUTION ERROR: {str(e)}"
            
            messages.append({"role": "user", "content": f"Command output:\n{output}"})
        else:
            messages.append({"role": "user", "content": "Please provide a bash command or the final answer in ```answer``` format."})
            
    print(f"  [-] Step limit ({MAX_STEPS_PER_TASK}) reached. Task not solved.")
    return False, total_task_cost

def main():
    parser = argparse.ArgumentParser(description="JiuwenGuard Agent Harness")
    parser.add_argument("--tasks-dir", type=str, required=True)
    args = parser.parse_args()
    
    tasks_dir = args.tasks_dir
    if not os.path.isdir(tasks_dir):
        print(f"Error: Directory {tasks_dir} not found.")
        sys.exit(1)
        
    print(f"Starting JiuwenGuard. Tasks directory: {tasks_dir}")
    print(f"Budget limit: {BUDGET_LIMIT}")
    
    tasks = []
    for folder_name in os.listdir(tasks_dir):
        task_path = os.path.join(tasks_dir, folder_name)
        if os.path.isdir(task_path):
            json_path = os.path.join(task_path, "task.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    data = clean_json_keys(raw_data)
                    data["_dir"] = task_path
                    data["_estimated_cost"] = estimate_task_cost(data.get("instruction", ""))
                    tasks.append(data)
                    
    # Сортировка: сначала самые выгодные (высокий reward / низкая estimated_cost)
    tasks.sort(key=lambda x: x.get("reward", 1) / max(x["_estimated_cost"], 1), reverse=True)
    print(f"Found {len(tasks)} tasks. Sorted by efficiency.")
    
    total_spent = 0.0
    total_reward = 0
    solved_count = 0
    
    for task in tasks:
        if total_spent >= BUDGET_LIMIT:
            print("Budget exhausted. Stopping.")
            break
            
        task_id = task.get("task_id", "unknown")
        reward = task.get("reward", 0)
        est_cost = task["_estimated_cost"]
        
        # Эвристика отсева подозрительно дорогих задач с низким reward
        if est_cost > 1000 and reward < 5:
            print(f"  [~] Skipping suspicious task {task_id} (High est. cost {est_cost:.1f}, low reward {reward})")
            continue
            
        print(f"\nTask: {task_id} (Reward: {reward}, Est. cost: {est_cost:.1f})")
        
        success, cost = solve_task(task["_dir"], task)
        total_spent += cost
        
        if success:
            total_reward += reward
            solved_count += 1
            
        print(f"Spent on task: {cost:.1f} | Total: {total_spent:.1f} / {BUDGET_LIMIT}")
        
    print("\n" + "="*50)
    print(f"DONE! Solved: {solved_count}/{len(tasks)}, Reward: {total_reward}, Cost: {total_spent:.1f}")
    print("="*50)

if __name__ == "__main__":
    main()
