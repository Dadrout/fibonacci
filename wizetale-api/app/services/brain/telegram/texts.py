"""Bot copy in English, Russian, and Kazakh."""
from __future__ import annotations

from typing import Optional

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "linked": "Connected ✓ Send me anything — slide photos, PDFs, links, voice notes — and I'll file it in your Brain.",
        "link_failed": "That code didn't work. Open Fibonacci → Brain → Telegram for a new one.",
        "how_to_link": "Hi! To connect, open Fibonacci → Brain → Telegram and send me the 6-digit code shown there.",
        "ready": "You're connected ✓ Forward me slide photos, PDFs, links, or voice notes and I'll file them in your Brain.",
        "got_it": "Got it — filing…",
        "filed": "Filed under {where} ✓",
        "new_link": "New connection: {link}",
        "failed": "I couldn't file this: {reason}",
        "too_large": "This file is over 20 MB. Send a smaller file or a link.",
        "unsupported": "I can read photos, PDFs, DOCX, text, audio, and links.",
        "error": "Something went wrong — please try again.",
        "reason.unsupported_type": "this file type isn't supported",
        "reason.too_large": "it's too large",
        "reason.unreadable": "I couldn't read any text in it",
        "reason.fetch_failed": "I couldn't open the link",
        "reason.transcript_unavailable": "the video has no transcript I can use",
        "reason.ai_unavailable": "the AI service is busy — open the web app and press Retry",
        "reason.internal": "something went wrong — open the web app and press Retry",
    },
    "ru": {
        "linked": "Подключено ✓ Присылайте что угодно — фото слайдов, PDF, ссылки, голосовые — я разложу всё в ваш Brain.",
        "link_failed": "Код не подошёл. Откройте Fibonacci → Brain → Telegram и получите новый.",
        "how_to_link": "Привет! Чтобы подключиться, откройте Fibonacci → Brain → Telegram и пришлите 6-значный код оттуда.",
        "ready": "Вы подключены ✓ Пересылайте мне фото слайдов, PDF, ссылки или голосовые — я разложу всё в ваш Brain.",
        "got_it": "Принято — раскладываю…",
        "filed": "Сохранено: {where} ✓",
        "new_link": "Новая связь: {link}",
        "failed": "Не получилось сохранить: {reason}",
        "too_large": "Файл больше 20 МБ. Пришлите файл поменьше или ссылку.",
        "unsupported": "Я понимаю фото, PDF, DOCX, текст, аудио и ссылки.",
        "error": "Что-то пошло не так — попробуйте ещё раз.",
        "reason.unsupported_type": "этот тип файла не поддерживается",
        "reason.too_large": "файл слишком большой",
        "reason.unreadable": "не удалось прочитать текст",
        "reason.fetch_failed": "не удалось открыть ссылку",
        "reason.transcript_unavailable": "у видео нет доступной расшифровки",
        "reason.ai_unavailable": "сервис ИИ занят — откройте веб-приложение и нажмите «Повторить»",
        "reason.internal": "что-то пошло не так — откройте веб-приложение и нажмите «Повторить»",
    },
    "kk": {
        "linked": "Қосылды ✓ Кез келген нәрсені жіберіңіз — слайд суреттері, PDF, сілтемелер, дауыстық хабарлар — бәрін Brain-ге реттеймін.",
        "link_failed": "Код жарамсыз. Fibonacci → Brain → Telegram бөлімін ашып, жаңа код алыңыз.",
        "how_to_link": "Сәлем! Қосылу үшін Fibonacci → Brain → Telegram бөлімін ашып, сондағы 6 таңбалы кодты жіберіңіз.",
        "ready": "Сіз қосылдыңыз ✓ Маған слайд суреттерін, PDF, сілтемелер немесе дауыстық хабарларды жіберіңіз — бәрін Brain-ге реттеймін.",
        "got_it": "Қабылдадым — реттеп жатырмын…",
        "filed": "Сақталды: {where} ✓",
        "new_link": "Жаңа байланыс: {link}",
        "failed": "Сақтау мүмкін болмады: {reason}",
        "too_large": "Файл 20 МБ-тан үлкен. Кішірек файл немесе сілтеме жіберіңіз.",
        "unsupported": "Мен сурет, PDF, DOCX, мәтін, аудио және сілтемелерді оқи аламын.",
        "error": "Бірдеңе дұрыс болмады — қайталап көріңіз.",
        "reason.unsupported_type": "бұл файл түріне қолдау жоқ",
        "reason.too_large": "файл тым үлкен",
        "reason.unreadable": "мәтінді оқу мүмкін болмады",
        "reason.fetch_failed": "сілтемені ашу мүмкін болмады",
        "reason.transcript_unavailable": "бейненің қолжетімді транскрипті жоқ",
        "reason.ai_unavailable": "ЖИ қызметі бос емес — веб-қосымшаны ашып, «Қайталау» түймесін басыңыз",
        "reason.internal": "бірдеңе дұрыс болмады — веб-қосымшаны ашып, «Қайталау» түймесін басыңыз",
    },
}


def lang(code: Optional[str]) -> str:
    code = (code or "").lower()
    return "ru" if code.startswith("ru") else "kk" if code.startswith("kk") else "en"


def t(language: str, key: str, **values: str) -> str:
    return TEXTS.get(language, TEXTS["en"]).get(key, TEXTS["en"][key]).format(**values)
