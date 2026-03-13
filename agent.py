import sys
import json
import os
from openai import OpenAI
from dotenv import load_dotenv
#dummi things
def main():
    # Загружаем переменные из .env.agent.secret
    load_dotenv('.env.agent.secret')

    # Проверяем, что пользователь передал вопрос
    if len(sys.argv) < 2:
        print("Error: Missing question argument.", file=sys.stderr)
        print("Usage: uv run agent.py \"Your question?\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Настраиваем клиента LLM
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen3-coder-plus")

    if not api_key or not base_url:
        print("Error: Missing LLM credentials in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        # Отправляем запрос в LLM
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful and concise assistant."},
                {"role": "user", "content": question}
            ]
        )
        
        # Достаем текст ответа
        answer_text = response.choices[0].message.content

        # Формируем требуемый JSON-формат
        output_data = {
            "answer": answer_text,
            "tool_calls": []
        }

        # Выводим ТОЛЬКО валидный JSON в stdout
        print(json.dumps(output_data))
        sys.exit(0) # Успешный код выхода

    except Exception as e:
        # Любые ошибки выводим в stderr
        print(f"Error calling LLM API: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()