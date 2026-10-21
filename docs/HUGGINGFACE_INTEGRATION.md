# 🎨 Интеграция Hugging Face для генерации изображений

## 📋 Обзор

Wizetale теперь использует **Hugging Face API** для генерации уникальных AI-изображений вместо стоковых фотографий. Это делает каждую историю более персонализированной и визуально привлекательной.

## 🔧 Настройка

### 1. Получение API ключа
1. Зарегистрируйтесь на [Hugging Face](https://huggingface.co/)
2. Перейдите в [Settings → Access Tokens](https://huggingface.co/settings/tokens)
3. Создайте новый токен с правами на чтение

### 2. Конфигурация
Добавьте ваш токен в переменные окружения:

```bash
# В wizetale-api/.env
HUGGINGFACE_API_KEY=hf_your_token_here
```

Или экспортируйте напрямую:
```bash
export HUGGINGFACE_API_KEY=hf_your_token_here
```

## 🎯 Используемые модели

### Основная модель
- **Stable Diffusion XL**: `stabilityai/stable-diffusion-xl-base-1.0`
  - Высокое качество изображений (1024x1024)
  - Хорошо понимает образовательный контент
  - Подходит для всех возрастов

### Fallback модели
- **Stable Diffusion 2.1**: `stabilityai/stable-diffusion-2-1`
- **Playground v2**: `playgroundai/playground-v2-1024px-aesthetic`

## 🔄 Архитектура с fallback

```
1. 🎨 Hugging Face AI Generation (приоритет)
   ↓ (если не удалось)
2. 📸 Pexels Stock Photos (fallback)
   ↓ (если и это не удалось)
3. 🖼️  Default Educational Images (последний fallback)
```

## 📊 Генерируемые промпты

### Для истории (History)
```
"Ancient Egypt, historical painting style, high quality, detailed, professional, educational, suitable for all ages"
```

### Для географии (Geography)
```
"Amazon Rainforest, nature photography style, high quality, detailed, professional, educational, suitable for all ages"
```

### Для философии (Philosophy)
```
"Wisdom and knowledge, classical painting style, high quality, detailed, professional, educational, suitable for all ages"
```

## 🛠️ API Endpoints

### Генерация видео с AI изображениями
```http
POST /api/v1/generate
Content-Type: application/json

{
  "subject": "history",
  "topic": "Ancient Egypt",
  "persona": "narrator",
  "language": "en",
  "user_id": 1
}
```

### Асинхронная генерация
```http
POST /api/v1/tasks/generate
Content-Type: application/json

{
  "subject": "geography",
  "topic": "Amazon Rainforest",
  "level": "beginner",
  "user_id": 1
}
```

## 📁 Структура файлов

```
wizetale-api/
├── app/
│   ├── services/
│   │   ├── huggingface_service.py  # 🆕 AI генерация
│   │   └── pexels_service.py       # Fallback
│   └── api/v1/
│       └── generate.py             # Обновлен для AI
├── generated_images/               # 🆕 AI изображения
│   ├── Ancient_Egypt_0_abc123.png
│   └── Amazon_Rainforest_1_def456.png
├── generated_videos/
└── generated_audio/
```

## 🧪 Тестирование

### Быстрый тест
```bash
python test_ai_images.py
```

### Ручное тестирование
```bash
cd wizetale-api
HUGGINGFACE_API_KEY=your_token uvicorn app.main:app --reload

# В другом терминале
curl -X POST "http://localhost:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "history",
    "topic": "Ancient Rome",
    "persona": "narrator",
    "language": "en",
    "user_id": 1
  }'
```

## 📈 Преимущества AI генерации

### ✅ Плюсы
- **Уникальность**: Каждое изображение генерируется специально для вашей истории
- **Релевантность**: AI понимает контекст и создает подходящие изображения
- **Качество**: Высокое разрешение (1024x1024) и профессиональный вид
- **Безопасность**: Подходит для всех возрастов, без проблем с авторскими правами
- **Бесплатность**: Hugging Face Inference API бесплатен для умеренного использования

### ⚠️ Ограничения
- **Время генерации**: 5-15 секунд на изображение
- **Лимиты API**: Hugging Face может ограничивать количество запросов
- **Качество**: Иногда может потребоваться несколько попыток для идеального результата

## 🔧 Настройка промптов

### Кастомизация для вашего контента
В файле `huggingface_service.py` можно настроить:

```python
def _enhance_prompt_for_education(self, topic: str, subject: str, style: str = "educational"):
    # Добавьте свои стили и модификаторы
    if subject.lower() == "science":
        style_additions = [
            "scientific illustration",
            "laboratory style",
            "educational diagram",
            "scientific accuracy"
        ]
```

## 📊 Мониторинг и логи

### Отслеживание генерации
```
🎨 Generating 8 AI images for 'Ancient Egypt' in history
  🖼️  Generating image 1/8: 'Ancient Egypt, historical painting style...'
    ✅ Generated and saved: /images/Ancient_Egypt_0_252cab09.png
  🖼️  Generating image 2/8: 'Ancient Egypt scene, medieval manuscript style...'
    ✅ Generated and saved: /images/Ancient_Egypt_1_81168a6c.png
📊 Successfully generated 8 out of 8 images
```

### Fallback логи
```
⚠️  AI generation failed or insufficient images, falling back to Pexels...
🔍 Searching Pexels for 'Ancient Egypt' in history (fallback)
✅ Found 6 Pexels images
```

## 🚀 Развертывание

### Production настройки
```bash
# Установите переменные окружения
export HUGGINGFACE_API_KEY=your_production_token
export ENVIRONMENT=production

# Запустите с Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker
```dockerfile
ENV HUGGINGFACE_API_KEY=your_token
```

## 🎯 Будущие улучшения

### Планируемые функции
- [ ] Кеширование сгенерированных изображений
- [ ] Пользовательские стили (cartoon, realistic, artistic)
- [ ] Batch генерация для ускорения
- [ ] Интеграция с другими AI моделями (DALL-E, Midjourney)
- [ ] Пользовательские промпты
- [ ] A/B тестирование качества изображений

### Оптимизации
- [ ] Предварительная генерация популярных тем
- [ ] CDN для быстрой доставки изображений
- [ ] Сжатие изображений для веба
- [ ] Адаптивные размеры для разных устройств

## 💡 Советы по использованию

1. **Специфичные промпты**: Чем детальнее тема, тем лучше результат
2. **Тестирование**: Попробуйте разные темы для оценки качества
3. **Fallback**: Всегда имейте запасной план (Pexels)
4. **Мониторинг**: Отслеживайте время генерации и успешность
5. **Кеширование**: Сохраняйте удачные изображения для повторного использования

## 🆘 Устранение неполадок

### Типичные проблемы

**Ошибка: "HUGGINGFACE_API_KEY is not set"**
```bash
# Решение
export HUGGINGFACE_API_KEY=your_token
```

**Ошибка: "Model is loading"**
```
# Решение: подождите 20-30 секунд, модель загружается
# Код автоматически повторит запрос
```

**Слишком долгая генерация**
```python
# Уменьшите количество изображений
images = await pipeline.generate_images_ai(topic, subject, story_text, count=4)
```

**Плохое качество изображений**
```python
# Попробуйте другую модель
self.default_model = self.models["playground"]
```

---

🎉 **Готово!** Ваш Wizetale теперь генерирует уникальные AI-изображения для каждой истории! 