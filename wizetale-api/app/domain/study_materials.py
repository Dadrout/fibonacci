"""Validated learner-owned study materials and quiz scoring."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain.models import QuizOption
from app.domain.teacher import PresentationSlide, StrictModel


StudentSubject = Literal['language_arts', 'math', 'science', 'history_social_studies', 'geography', 'philosophy']


StudyMaterialKind = Literal['flashcards', 'quiz', 'presentation']
StudyLanguage = Literal['en-US', 'ru-RU', 'kk-KZ']


class StudyContext(StrictModel):
    subject: StudentSubject
    grade: str = Field(pattern=r'^(K|[1-9]|1[0-2])$')
    topic: str = Field(min_length=1, max_length=200)
    language: StudyLanguage = 'en-US'
    source_text: str = Field(default='', max_length=20000)

    @field_validator('topic')
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return ' '.join(value.split())


class StudyFlashcard(StrictModel):
    front: str = Field(min_length=1, max_length=1500)
    back: str = Field(min_length=1, max_length=2000)


class StudyQuestion(StrictModel):
    prompt: str = Field(min_length=1, max_length=2000)
    options: list[QuizOption] = Field(min_length=3, max_length=4)
    correct_option: Literal['a', 'b', 'c', 'd']
    explanation: str = Field(min_length=1, max_length=3000)

    @model_validator(mode='after')
    def validate_answer_option(self):
        ids = [option.id for option in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError('Quiz option identifiers must be distinct')
        if self.correct_option not in ids:
            raise ValueError('Correct answer must match one of the options')
        return self


class StudyMaterialContent(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    instructions: str = Field(default='', max_length=4000)
    flashcards: list[StudyFlashcard] = Field(default_factory=list, max_length=100)
    questions: list[StudyQuestion] = Field(default_factory=list, max_length=100)
    slides: list[PresentationSlide] = Field(default_factory=list, max_length=24)


class StudyMaterialGenerate(StrictModel):
    kind: StudyMaterialKind
    request_id: UUID
    context: StudyContext


class StudyMaterialUpdate(StrictModel):
    content: StudyMaterialContent
    revision: int = Field(ge=1)


def validate_study_content(
    kind: StudyMaterialKind,
    content: StudyMaterialContent,
    *,
    generated: bool = False,
) -> StudyMaterialContent:
    if kind == 'flashcards' and not content.flashcards:
        raise ValueError('Add at least one flashcard')
    if kind == 'quiz' and not content.questions:
        raise ValueError('A quiz needs questions')
    if kind == 'presentation' and len(content.slides) != 8:
        raise ValueError('A presentation needs exactly 8 slides')
    if generated:
        expected = {'flashcards': 12, 'quiz': 10, 'presentation': 8}[kind]
        actual = {
            'flashcards': len(content.flashcards),
            'quiz': len(content.questions),
            'presentation': len(content.slides),
        }[kind]
        if actual != expected:
            raise ValueError(f'Generate {expected} {kind}')
    return content


def score_quiz(content: StudyMaterialContent, answers: dict[str, str]) -> dict:
    questions = content.questions
    expected_keys = {str(index) for index in range(1, len(questions) + 1)}
    if not questions or set(answers) != expected_keys:
        raise ValueError('Submit one answer for every question')
    results = []
    for index, question in enumerate(questions, start=1):
        answer = answers[str(index)]
        option_ids = {option.id for option in question.options}
        if answer not in option_ids:
            raise ValueError('Choose a valid answer for every question')
        results.append({
            'question_number': index,
            'correct': answer == question.correct_option,
            'correct_option': question.correct_option,
            'explanation': question.explanation,
        })
    return {'score': sum(item['correct'] for item in results), 'total': len(results), 'results': results}
