from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Выберите модель (доступные варианты):
# - deepseek-ai/deepseek-r1-distill-qwen-1.5b
# - deepseek-ai/deepseek-r1-distill-llama-8b
# - deepseek-ai/deepseek-r1-14b (требует больше памяти)

model_name = "deepseek-ai/deepseek-r1-distill-llama-8b"

print(f"Загрузка модели {model_name}...")

# Загрузка токенизатора и модели
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)

print("Модель загружена успешно!")

# Тестовый запрос
prompt = "Объясни, что такое искусственный интеллект:"
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

# Генерация ответа
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_length=200,
        temperature=0.7,
        do_sample=True
    )

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print("\n" + "="*50)
print("Ответ модели:")
print("="*50)
print(response)
