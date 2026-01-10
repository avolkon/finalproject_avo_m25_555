# r1.py - версия с Reasoning
import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()

class DeepSeekR1:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY не найден в .env")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
        
        self.messages = []
        self.reasoning_history = []
    
    def show_welcome(self):
        print("=" * 60)
        print("🚀 DeepSeek R1 Reasoning Model")
        print("=" * 60)
        print("Команды:")
        print("  /clear - очистить историю")
        print("  /reason - показать цепочку рассуждений")
        print("  exit   - выйти")
        print("=" * 60)
    
    def chat(self):
        self.show_welcome()
        
        while True:
            try:
                user_input = input("\n👤 Вы: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 До свидания!")
                    break
                
                elif user_input == '/clear':
                    self.messages.clear()
                    self.reasoning_history.clear()
                    print("🗑️ История очищена!")
                    continue
                
                elif user_input == '/reason':
                    self.show_reasoning()
                    continue
                
                # Отправляем запрос с reasoning
                self.messages.append({"role": "user", "content": user_input})
                
                print("\n" + "🤖 " + "─" * 40)
                
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=self.messages,
                    stream=True
                )
                
                assistant_response = ""
                print("💭 ", end="", flush=True)
                
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end="", flush=True)
                        assistant_response += content
                
                if assistant_response:
                    self.messages.append({"role": "assistant", "content": assistant_response})
                    self.reasoning_history.append({
                        "question": user_input,
                        "reasoning": assistant_response
                    })
                
                print("\n" + "─" * 50)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Прервано пользователем")
                break
            except Exception as e:
                print(f"\n❌ Ошибка: {e}")
    
    def show_reasoning(self):
        if not self.reasoning_history:
            print("📭 История рассуждений пуста")
            return
        
        print("\n" + "🧠 " + "=" * 40)
        print("ИСТОРИЯ РАССУЖДЕНИЙ:")
        print("=" * 40)
        
        for i, item in enumerate(self.reasoning_history, 1):
            print(f"\n{i}. Вопрос: {item['question']}")
            print(f"   Ответ: {item['reasoning'][:200]}...")
        print("=" * 40)

if __name__ == "__main__":
    try:
        bot = DeepSeekR1()
        bot.chat()
    except ValueError as e:
        print(f"❌ {e}")
        print("📝 Создайте файл .env с ключом:")
        print('DEEPSEEK_API_KEY="ваш_ключ_здесь"')

        