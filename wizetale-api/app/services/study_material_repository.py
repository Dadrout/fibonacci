"""Private server-side persistence for learner-owned study materials."""

from app.services.story_repository import SupabaseStoryRepository
from app.services.presentation_visuals import text_content


class StudyMaterialRepository(SupabaseStoryRepository):
    def materials(self, user_id: str, limit: int, offset: int):
        return self._request(
            'GET', 'student_study_materials',
            params={
                'user_id': f'eq.{user_id}', 'order': 'created_at.desc',
                'select': '*', 'limit': str(limit), 'offset': str(offset),
            },
        )

    def material(self, material_id: str, user_id: str):
        rows = self._request(
            'GET', 'student_study_materials',
            params={'id': f'eq.{material_id}', 'user_id': f'eq.{user_id}', 'select': '*', 'limit': '1'},
        )
        return rows[0] if rows else None

    def claim_material(self, record: dict):
        rows = self._request(
            'POST', 'student_study_materials', params={'on_conflict': 'id'}, payload=record,
            prefer='resolution=ignore-duplicates,return=representation',
        )
        return rows[0] if rows else None

    def finish_material(self, material_id: str, user_id: str, changes: dict):
        rows = self._request(
            'PATCH', 'student_study_materials',
            params={'id': f'eq.{material_id}', 'user_id': f'eq.{user_id}', 'status': 'eq.generating'},
            payload=changes, prefer='return=representation',
        )
        return rows[0] if rows else None

    def update_material(self, material_id: str, user_id: str, revision: int, content: dict):
        rows = self._request(
            'PATCH', 'student_study_materials',
            params={'id': f'eq.{material_id}', 'user_id': f'eq.{user_id}', 'revision': f'eq.{revision}', 'status': 'eq.ready'},
            payload={'content': text_content(content), 'revision': revision + 1}, prefer='return=representation',
        )
        return rows[0] if rows else None

    def delete_material(self, material_id: str, user_id: str):
        self._request(
            'DELETE', 'student_study_materials',
            params={'id': f'eq.{material_id}', 'user_id': f'eq.{user_id}'},
        )


study_material_repository = StudyMaterialRepository()
