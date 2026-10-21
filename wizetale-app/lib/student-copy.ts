import type { Language } from './i18n'
import { copyText } from './copy'

const studentCopy: Record<string, [string, string]> = {
  'Learning workspace': ['Учебная мастерская', 'Оқу шеберханасы'],
  'Create': ['Создать', 'Жасау'],
  'Study': ['Учиться', 'Оқу'],
  'My Work': ['Мои работы', 'Жұмыстарым'],
  'One topic, many ways to learn.': ['Одна тема — много способов учиться.', 'Бір тақырып, үйренудің түрлі жолдары.'],
  'Choose a subject, add your question, and pick how you want to learn.': ['Выберите предмет, добавьте вопрос и способ изучения.', 'Пәнді таңдап, сұрағыңызды жазып, оқу тәсілін таңдаңыз.'],
  'Choose your format': ['Выберите формат', 'Пішінді таңдаңыз'],
  'Story / video': ['История / видео', 'Әңгіме / бейне'],
  'Preview a story, then create its video': ['Измените историю и создайте видео', 'Әңгімені қарап, бейнесін жасаңыз'],
  'Saved work': ['Сохранённые работы', 'Сақталған жұмыстар'],
  'Show saved work': ['Открыть сохранённые работы', 'Сақталған жұмыстарды ашу'],
  'Hide saved work': ['Скрыть сохранённые работы', 'Сақталған жұмыстарды жасыру'],
  'Your stories and study materials, together.': ['Ваши истории и учебные материалы вместе.', 'Әңгімелеріңіз бен оқу құралдарыңыз бір жерде.'],
  'Your topic and language are shared across all four formats.': ['Тема и язык общие для всех четырёх форматов.', 'Тақырып пен тіл төрт пішінге де ортақ.'],
  'Your work stays open when you switch formats.': ['Работа остаётся открытой при смене формата.', 'Пішінді ауыстырғанда жұмысыңыз ашық қалады.'],
  'Generation in progress. You can switch formats while it finishes.': ['Идёт создание. Можно переключить формат, пока оно завершается.', 'Жасалуда. Аяқталғанша басқа пішінге ауыса аласыз.'],
  'Back to story draft': ['Вернуться к черновику истории', 'Әңгіме жобасына оралу'],
  'Slide visual': ['Иллюстрация слайда', 'Слайд көрнекілігі'],
  'Visual ready': ['Иллюстрация готова', 'Көрнекілік дайын'],
  'Visual failed': ['Не удалось создать иллюстрацию', 'Көрнекілік жасалмады'],
  'Creating visual…': ['Создание иллюстрации…', 'Көрнекілік жасалуда…'],
  'Visual queued': ['Иллюстрация в очереди', 'Көрнекілік кезекте'],
  'No visual': ['Нет иллюстрации', 'Көрнекілік жоқ'],
  'Updating visual…': ['Обновление иллюстрации…', 'Көрнекілік жаңартылуда…'],
  'Create visual': ['Создать иллюстрацию', 'Көрнекілік жасау'],
  'Retry visual': ['Повторить создание иллюстрации', 'Көрнекілікті қайта жасау'],
  'Remove visual': ['Удалить иллюстрацию', 'Көрнекілікті жою'],
  'Could not refresh slide visuals. Try again.': ['Не удалось обновить иллюстрации. Повторите попытку.', 'Слайд көрнекіліктерін жаңарту мүмкін болмады. Қайталап көріңіз.'],
  'Could not update slide visual. Try again.': ['Не удалось изменить иллюстрацию слайда. Повторите попытку.', 'Слайд көрнекілігін өзгерту мүмкін болмады. Қайталап көріңіз.'],
  'Save your slide edits before changing visuals.': ['Сохраните изменения слайдов перед изменением иллюстраций.', 'Көрнекіліктерді өзгертпес бұрын слайд түзетулерін сақтаңыз.'],
}
export function studentCopyText(text: string, language: Language) {
  const localized=studentCopy[text]
  return localized&&language!=='en'?localized[language==='ru'?0:1]:copyText(text,language)
}
