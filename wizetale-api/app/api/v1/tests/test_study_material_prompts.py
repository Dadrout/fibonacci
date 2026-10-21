import importlib.util

import pytest


def modules():
    assert importlib.util.find_spec('app.services.study_material_generation') is not None, 'Student material generation service is missing'
    from app.domain.study_materials import StudyMaterialContent
    from app.services import study_material_generation
    return StudyMaterialContent, study_material_generation


class CapturingProvider:
    def __init__(self, response):
        self.response = response
        self.call = None

    def generate_structured(self, **kwargs):
        self.call = kwargs
        return self.response


def context(language='kk-KZ', grade='6', subject='math', topic='Fractions'):
    from app.domain.study_materials import StudyContext
    return StudyContext(subject=subject, grade=grade, language=language, topic=topic)


@pytest.mark.parametrize('kind', ['flashcards', 'quiz', 'presentation'])
@pytest.mark.parametrize('language,grade,subject,topic', [
    ('en-US', 'K', 'language_arts', 'Rhyming words'),
    ('ru-RU', '6', 'science', 'Food chains'),
    ('kk-KZ', '12', 'history_social_studies', 'Silk Road trade'),
])
def test_student_generation_uses_topic_grade_and_output_language(monkeypatch, kind, language, grade, subject, topic):
    content_model, service_module = modules()
    if kind == 'flashcards':
        payload = {'title': topic, 'flashcards': [{'front': f'Prompt {i}', 'back': 'A short answer.'} for i in range(12)]}
    elif kind == 'quiz':
        payload = {'title': topic, 'questions': [{
            'prompt': f'Question {i}',
            'options': [{'id': choice, 'text': f'Choice {choice}'} for choice in 'abcd'],
            'correct_option': 'a',
            'explanation': 'The first option is correct.',
        } for i in range(10)]}
    else:
        payload = {'title': topic, 'slides': [{
            'title': f'Slide {i}', 'key_points': ['One clear idea.'], 'speaker_notes': 'Explain the idea.',
        } for i in range(8)]}
    provider = CapturingProvider(content_model.model_validate(payload))
    monkeypatch.setattr(service_module, 'get_text_provider', lambda: provider)

    result = service_module.StudyMaterialGenerationService().generate(context(language, grade, subject, topic), kind)

    assert result.title == topic
    prompt = provider.call['prompt'].lower()
    assert topic.lower() in prompt
    assert f'grade: {grade.lower()}' in prompt
    assert language.lower() in prompt
    assert kind in prompt
