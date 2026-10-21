"""Server-only persistence. Every read/write includes the authenticated owner."""
from app.services.story_repository import SupabaseStoryRepository
from app.services.presentation_visuals import text_content


class TeacherRepository(SupabaseStoryRepository):
    def _one(self, table, filters):
        rows = self._request('GET', table, params={**filters, 'select': '*', 'limit': '1'})
        return rows[0] if rows else None

    def profile(self, uid):
        return self._one('teacher_profiles', {'user_id': f'eq.{uid}'})

    def enable_teacher(self, uid):
        rows = self._request('POST', 'teacher_profiles', params={'on_conflict': 'user_id'}, payload={'user_id': uid}, prefer='resolution=ignore-duplicates,return=representation')
        return rows[0] if rows else self.profile(uid)

    def lessons(self, uid, limit, offset):
        return self._request('GET', 'teacher_lessons', params={'user_id': f'eq.{uid}', 'order': 'updated_at.desc', 'limit': str(limit), 'offset': str(offset), 'select': 'id,user_id,subject,grade,topic,language,revision,created_at,updated_at'})

    def lesson(self, lid, uid):
        return self._one('teacher_lessons', {'id': f'eq.{lid}', 'user_id': f'eq.{uid}'})

    def create_lesson(self, record):
        return self._request('POST', 'teacher_lessons', payload=record, prefer='return=representation')[0]

    def update_lesson(self, lid, uid, revision, data):
        rows = self._request('PATCH', 'teacher_lessons', params={'id': f'eq.{lid}', 'user_id': f'eq.{uid}', 'revision': f'eq.{revision}'}, payload={**data, 'revision': revision+1}, prefer='return=representation')
        return rows[0] if rows else None

    def delete_lesson(self, lid, uid):
        self._request('DELETE', 'teacher_lessons', params={'id': f'eq.{lid}', 'user_id': f'eq.{uid}'})

    def resources(self, lid, uid, limit, offset):
        return self._request('GET', 'teacher_resources', params={'lesson_id': f'eq.{lid}', 'user_id': f'eq.{uid}', 'order': 'created_at.desc', 'select': '*', 'limit': str(limit), 'offset': str(offset)})

    def resource(self, rid, uid):
        return self._one('teacher_resources', {'id': f'eq.{rid}', 'user_id': f'eq.{uid}'})

    def claim_resource(self, record):
        rows = self._request('POST', 'teacher_resources', params={'on_conflict': 'id'}, payload=record, prefer='resolution=ignore-duplicates,return=representation')
        return rows[0] if rows else None

    def finish_resource(self, rid, uid, changes):
        rows = self._request('PATCH', 'teacher_resources', params={'id': f'eq.{rid}', 'user_id': f'eq.{uid}', 'status': 'eq.generating'}, payload=changes, prefer='return=representation')
        return rows[0] if rows else None

    def expire_stalled_resource(self, rid, uid, cutoff):
        rows = self._request('PATCH', 'teacher_resources', params={
            'id': f'eq.{rid}', 'user_id': f'eq.{uid}',
            'status': 'eq.generating', 'updated_at': f'lt.{cutoff}',
        }, payload={'status': 'failed'}, prefer='return=representation')
        return rows[0] if rows else None

    def update_resource(self, rid, uid, revision, content):
        rows = self._request('PATCH', 'teacher_resources', params={'id': f'eq.{rid}', 'user_id': f'eq.{uid}', 'revision': f'eq.{revision}', 'status': 'eq.ready'}, payload={'content': text_content(content), 'revision': revision+1}, prefer='return=representation')
        return rows[0] if rows else None

    def delete_resource(self, rid, uid):
        self._request('DELETE', 'teacher_resources', params={'id': f'eq.{rid}', 'user_id': f'eq.{uid}'})


teacher_repository = TeacherRepository()
