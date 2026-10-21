export type Language = 'en' | 'ru' | 'kk'

export type BaseTranslations = {
  signIn: string
  title: string
  subtitle: string
  storyGenerator: string
  subject: string
  chooseSubject: string
  history: string
  customStory: string
  storyTitle: string
  storyDescription: string
  enhanceWithAI: string
  voice: string
  generateStory: string
  yourStoryVideo: string
  videoPlaceholder: string
  videoSubtitle: string
  transcript: string
  show: string
  hide: string
  topic: string;
  topicPlaceholder: string;
  femaleVoice: string;
  maleVoice: string;
  language: string;
  english: string;
  russian: string;
  generatingStory: string;
  generateVideo: string;
  allRightsReserved: string;
  literature: string;
}

// Allow additional keys without updating the type every time
export type Translations = BaseTranslations & Record<string, string>;

// TEMP: reuse full translation set from former landing package until we consolidate
import fullTranslations from "./fullTranslations";
import { kazakhTranslations } from "./kazakh-translations";

const baseEN: BaseTranslations = {
  signIn: "Sign In",
  title: "Generate educational stories with AI",
  subtitle: "Turn any topic into an engaging animated video story. Perfect for learning and discovery.",
  storyGenerator: "Story Generator",
  subject: "Subject",
  chooseSubject: "Choose a subject",
  history: "History",
  customStory: "Custom Story",
  storyTitle: "Story Title",
  storyDescription: "Story Description",
  enhanceWithAI: "Enhance with AI",
  voice: "Voice",
  generateStory: "Generate Story",
  yourStoryVideo: "Your Story Video",
  videoPlaceholder: "Your video will appear here",
  videoSubtitle: "Select a topic and generate your story",
  transcript: "Transcript",
  show: "Show",
  hide: "Hide",
  topic: "Topic",
  topicPlaceholder: "Enter a topic (e.g. The Roman Empire)",
  femaleVoice: "Female Voice",
  maleVoice: "Male Voice",
  language: "Language",
  english: "English",
  russian: "Russian",
  generatingStory: "Generating story...",
  generateVideo: "Generate Video",
  allRightsReserved: "All rights reserved.",
  literature: "Literature",
};

const baseRU: BaseTranslations = {
  signIn: "Войти",
  title: "Создавайте обучающие истории с помощью ИИ",
  subtitle: "Преобразуйте любую тему в увлекательное анимированное видео.",
  storyGenerator: "Генератор историй",
  subject: "Предмет",
  chooseSubject: "Выберите предмет",
  history: "История",
  customStory: "Своя история",
  storyTitle: "Название истории",
  storyDescription: "Описание истории",
  enhanceWithAI: "Улучшить ИИ",
  voice: "Голос",
  generateStory: "Сгенерировать историю",
  yourStoryVideo: "Ваше видео",
  videoPlaceholder: "Ваше видео появится здесь",
  videoSubtitle: "Выберите тему и сгенерируйте историю",
  transcript: "Сценарий",
  show: "Показать",
  hide: "Скрыть",
  topic: "Тема",
  topicPlaceholder: "Введите тему (например, Римская империя)",
  femaleVoice: "Женский голос",
  maleVoice: "Мужской голос",
  language: "Язык",
  english: "Английский",
  russian: "Русский",
  generatingStory: "Генерация истории...",
  generateVideo: "Сгенерировать видео",
  allRightsReserved: "Все права защищены.",
  literature: "Литература",
};

const translations: Record<Language, Translations> = {
  en: { ...baseEN, ...(fullTranslations.en as any) },
  ru: { ...baseRU, ...(fullTranslations.ru as any) },
  kk: kazakhTranslations,
};

export const getTranslation = (lang: Language): Translations => {
  return translations[lang] || translations.en
}
