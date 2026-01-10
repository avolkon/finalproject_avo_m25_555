# main.py - базовая версия
import os
from dotenv import load_dotenv
from openai import OpenAI
import json

# Загружаем переменные окружения
load_dotenv()

# Получаем API ключ
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    print("❌ Ошибка: DEEPSEEK_API_KEY не найден в файле .env")
    print("Добавьте ключ в файл .env:")
    print('DEEPSEEK_API_KEY="ваш_ключ"')
    exit(1)

# Создаем клиент
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

print("🤖 DeepSeek R1 запущен!")
print("Введите ваш запрос (или 'exit' для выхода):")
print("-" * 50)

# История сообщений
messages = []

while True:
    user_input = input("\n👤 Вы: ").strip()
    
    if user_input.lower() in ['exit', 'quit', 'выход']:
        print("👋 До свидания!")
        break
    
    # Добавляем сообщение пользователя
    messages.append({"role": "user", "content": user_input})
    
    print("\n🤖 DeepSeek думает...")
    
    try:
        # Отправляем запрос
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True
        )
        
        # Собираем ответ по частям
        assistant_response = ""
        print("🤖 DeepSeek: ", end="", flush=True)
        
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                assistant_response += content
        
        # Добавляем ответ в историю
        if assistant_response:
            messages.append({"role": "assistant", "content": assistant_response})
        
        print()  # Новая строка
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

        