from copy import deepcopy
from pathlib import Path
import pytest


def service_module():
    import importlib.util
    assert importlib.util.find_spec('app.services.presentation_visuals'), 'Presentation visual lifecycle is missing'
    from app.services import presentation_visuals
    return presentation_visuals


def material():
    return {'id': 'deck', 'user_id': 'learner', 'kind': 'presentation', 'status': 'ready', 'revision': 4,
            'subject': 'science', 'grade': '5', 'topic': 'Water cycle', 'language': 'en-US',
            'content': {'title': 'Water cycle', 'slides': [{'title': f'Stage {i}', 'key_points': [f'Water stage {i}'], 'speaker_notes': f'Explain stage {i}.'} for i in range(8)]}}


class MemoryStore:
    def __init__(self): self.rows = {}
    def list(self, kind, deck_id, uid): return [deepcopy(r) for r in self.rows.values() if (r['deck_type'], r['deck_id'], r['user_id']) == (kind, deck_id, uid)]
    def save(self, row): self.rows[(row['deck_type'],row['deck_id'],row['user_id'],row['slide_index'])] = deepcopy(row); return deepcopy(row)
    def get(self, kind, deck_id, uid, index): return next((r for r in self.list(kind,deck_id,uid) if r['slide_index']==index), None)
    def transition(self, row, status, **changes):
        current = self.get(row['deck_type'],row['deck_id'],row['user_id'],row['slide_index'])
        if not current or current['id'] != row['id'] or current['status'] != row['status']: return None
        current.update(status=status, **changes)
        return self.save(current)
    def remove(self, kind, deck_id, uid, index): self.rows.pop((kind,deck_id,uid,index),None)


class MemoryMedia:
    def __init__(self): self.objects = {}; self.deleting = False
    def is_user_deleting(self, uid): return self.deleting
    def upload_asset(self, *, object_path, local_path, content_type): self.objects[object_path] = Path(local_path).read_bytes(); return object_path
    def create_signed_asset_url(self, path): return 'signed:' + path
    def delete_asset(self, path): self.objects.pop(path, None)


@pytest.fixture
def env(tmp_path):
    module = service_module()
    store, media, scheduled = MemoryStore(), MemoryMedia(), []
    service = module.PresentationVisualService(repository=store, media=media, enqueue=lambda row: scheduled.append(row), workdir=tmp_path)
    return module, service, store, media, scheduled


def test_saved_deck_gets_three_pending_visuals_without_content_revision_change(env):
    _, service, store, _, scheduled = env
    deck = material(); original = deepcopy(deck)
    service.queue(deck, 'student')
    assert deck == original
    assert len(scheduled) == 3
    public = service.decorate(deck, 'student')
    assert public['revision'] == 4
    selected = [slide['visual'] for slide in public['content']['slides'] if slide.get('visual')]
    assert len(selected) == 3
    assert all(v['status'] == 'pending' and v['image_url'] is None for v in selected)
    assert set(selected[0]) == {'status', 'kind', 'alt_text', 'caption', 'image_url'}
    assert service.decorate({**deck,'user_id':'other'}, 'student')['content'] == original['content']
    assert len(store.list('student','deck','learner')) == 3


def test_failed_images_keep_text_ready_and_owner_can_retry(env):
    _, service, _, media, scheduled = env
    deck = material(); service.queue(deck,'student'); row = scheduled[0]
    class Failed:
        def generate_image(self, **kwargs): return None
    service.process(row, Failed())
    public = service.decorate(deck,'student')
    assert public['status'] == 'ready'
    assert public['content']['slides'][row['slide_index']]['visual']['status'] == 'failed'
    retry = service.retry(deck,'student',row['slide_index'])
    assert retry['status'] == 'pending' and retry['id'] != row['id']
    assert public['revision'] == 4 and not media.objects


def test_ready_images_are_private_signed_and_removal_cancels_stale_worker(env):
    _, service, store, media, scheduled = env
    deck = material(); service.queue(deck,'teacher'); row=scheduled[0]
    class Provider:
        def generate_image(self, **kwargs):
            Path(kwargs['output_path']).write_bytes(b'image')
            return kwargs['output_path']
    service.process(row, Provider())
    public=service.decorate(deck,'teacher')
    visual=public['content']['slides'][row['slide_index']]['visual']
    assert visual['status']=='ready' and visual['image_url'].startswith('signed:learner/')
    assert public['revision']==4
    service.remove(deck,'teacher',row['slide_index'])
    assert not media.objects
    assert not service.decorate(deck,'teacher')['content']['slides'][row['slide_index']].get('visual')
    service.process(row,Provider())
    assert not media.objects


def test_removing_during_image_generation_does_not_publish_or_leave_asset(env):
    _,service,_,media,scheduled=env
    deck=material();service.queue(deck,'student');row=scheduled[0]
    class Provider:
        def generate_image(self,**kwargs):
            service.remove(deck,'student',row['slide_index'])
            Path(kwargs['output_path']).write_bytes(b'image')
            return kwargs['output_path']
    service.process(row,Provider())
    assert not media.objects
    assert not service.decorate(deck,'student')['content']['slides'][row['slide_index']].get('visual')


def test_visuals_are_not_queued_before_ready_text_and_cleanup_removes_assets(env):
    _,service,store,media,scheduled=env
    deck=material();service.queue({**deck,'status':'generating'},'student');assert scheduled==[]
    service.queue(deck,'student')
    class Provider:
        def generate_image(self,**kwargs): Path(kwargs['output_path']).write_bytes(b'image');return kwargs['output_path']
    service.process(scheduled[0],Provider())
    service.cleanup(deck,'student')
    assert not store.list('student','deck','learner') and not media.objects


def test_retry_limit_and_account_deletion_prevent_image_generation(env):
    _,service,_,media,scheduled=env
    deck=material();service.queue(deck,'student')
    with pytest.raises(ValueError): service.retry(deck,'student',0)
    media.deleting=True
    class Provider:
        def generate_image(self,**kwargs): raise AssertionError('Deleting account must not generate')
    service.process(scheduled[0],Provider())
    assert not media.objects


def test_teacher_visual_changes_invalidate_video_without_text_revision_change(env):
    _,service,_,media,scheduled=env
    invalidated=[]
    media.invalidate_presentation_renders=lambda deck_id,uid:invalidated.append((deck_id,uid))
    deck=material();service.queue(deck,'teacher')
    class Provider:
        def generate_image(self,**kwargs): Path(kwargs['output_path']).write_bytes(b'image');return kwargs['output_path']
    service.process(scheduled[0],Provider())
    assert ('deck','learner') in invalidated
    invalidated.clear()
    service.remove(deck,'teacher',scheduled[0]['slide_index'])
    assert invalidated==[('deck','learner')]
    assert deck['revision']==4


def test_visual_frame_composes_image_and_falls_back_for_missing_image(tmp_path):
    from PIL import Image
    from app.services.teacher_presentation_video import render_slide_image
    asset=tmp_path/'asset.png';Image.new('RGB',(640,360),'#ff0000').save(asset)
    frame=tmp_path/'frame.png'
    render_slide_image(title='Evaporation',key_points=['Water becomes vapor.'],index=1,total=8,topic='Water cycle',output_path=str(frame),visual_path=str(asset))
    with Image.open(frame) as image:
        assert image.size==(1280,720)
        assert image.getpixel((1000,350))==(255,0,0)
    render_slide_image(title='Evaporation',key_points=['Water becomes vapor.'],index=1,total=8,topic='Water cycle',output_path=str(frame),visual_path=str(tmp_path/'missing.png'))
    assert frame.exists()
