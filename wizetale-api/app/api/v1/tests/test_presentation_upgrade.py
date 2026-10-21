import pytest
from pydantic import ValidationError
from app.domain.study_materials import StudyContext, StudyMaterialContent, validate_study_content
from app.domain.models import StoryDraftRequest
from app.domain.teacher import LessonInput, ResourceContent, validate_content

SUBJECTS = ['language_arts', 'math', 'science', 'history_social_studies', 'geography', 'philosophy']

def deck(model=StudyMaterialContent):
    return model(title='Water cycle', slides=[{'title': f'Step {i}', 'key_points': [f'Water stage {i}'], 'speaker_notes': f'Explain water stage {i}.'} for i in range(8)])

@pytest.mark.parametrize('subject', SUBJECTS)
def test_all_student_subjects_support_study_and_story(subject):
    assert StudyContext(subject=subject, grade='5', topic='Learning').subject == subject
    assert StoryDraftRequest(subject=subject, topic='Learning').subject == subject

def test_teacher_subjects_stay_unchanged():
    with pytest.raises(ValidationError):
        LessonInput(subject='philosophy', grade='5', topic='Ethics')

@pytest.mark.parametrize('model,validator', [(StudyMaterialContent, validate_study_content), (ResourceContent, validate_content)])
def test_editing_presentation_preserves_eight_slides(model, validator):
    content = deck(model)
    content.slides.pop()
    with pytest.raises(ValueError, match='8'):
        validator('presentation', content)

def test_presentation_quality_repair_is_bounded_and_failure_keeps_valid_draft(monkeypatch):
    from app.services import study_material_generation as module
    class Provider:
        def __init__(self): self.calls = []
        def generate_structured(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 2: raise RuntimeError('provider unavailable')
            return deck()
    provider = Provider()
    monkeypatch.setattr(module, 'get_text_provider', lambda: provider)
    result = module.StudyMaterialGenerationService().generate(StudyContext(subject='science', grade='5', topic='Water cycle'), 'presentation')
    assert len(result.slides) == 8
    assert len(provider.calls) == 2
    assert 'critique' in provider.calls[1]['prompt'].lower()
    assert 'accuracy' in provider.calls[1]['prompt'].lower()


def test_visual_metadata_is_accepted_but_not_persisted_with_text():
    from app.services.presentation_visuals import text_content
    payload=deck().model_dump()
    payload['slides'][1]['visual']={'status':'failed','kind':'diagram','alt_text':'Water','caption':'Water','image_url':'https://example.test/image'}
    parsed=StudyMaterialContent.model_validate(payload)
    assert 'visual' not in text_content(parsed.model_dump())['slides'][1]


def test_teacher_presentation_repair_keeps_grounding_and_provenance(monkeypatch):
    from app.services import teacher_generation as module
    from app.services.teacher_retrieval import GroundedResource
    lesson={'subject':'science','grade':'5','topic':'Water cycle','language':'en-US','objectives':'Explain stages','source_material':''}
    passages=[{'passage_id':'p1','document_id':None,'title':'Notes','location':'Class','text':'Water evaporates.'}]
    class Provider:
        def __init__(self): self.calls=[]
        def generate_structured(self,**kwargs):
            self.calls.append(kwargs)
            return GroundedResource(sufficient=True,content=deck(ResourceContent),passage_ids=['p1'])
    provider=Provider();monkeypatch.setattr(module,'get_text_provider',lambda:provider)
    content,provenance=module.TeacherGenerationService().generate(lesson,'presentation',passages)
    assert len(content.slides)==8 and provenance['status']=='source_based'
    assert len(provider.calls)==2
    assert 'All factual content must come from the supplied passages' in provider.calls[1]['prompt']
    assert 'p1' in provider.calls[1]['prompt']


def test_private_visual_asset_removal_targets_one_object(monkeypatch):
    from app.services.story_repository import SupabaseStoryRepository
    from app.core.config import settings
    monkeypatch.setattr(settings,'MEDIA_STORAGE_PROVIDER','supabase')
    monkeypatch.setattr(settings,'SUPABASE_URL','https://example.test')
    monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','test-key')
    class Response:
        content=b'[]'
        def raise_for_status(self): pass
        def json(self): return []
    class Session:
        def __init__(self): self.calls=[]
        def delete(self,url,**kwargs): self.calls.append(kwargs); return Response()
    session=Session(); repository=SupabaseStoryRepository(session=session)
    assert hasattr(repository,'delete_asset'), 'Private visual object cleanup is missing'
    repository.delete_asset('owner/task/slide.png')
    assert session.calls[0]['json']=={'prefixes':['owner/task/slide.png']}
