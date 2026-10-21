"""Owner-scoped document persistence and original-file storage."""
from contextlib import contextmanager
from urllib.parse import quote

import redis

from app.core.config import settings
from app.services.teacher_repository import TeacherRepository

BUCKET = 'teacher-documents'


class DocumentRepository(TeacherRepository):
    def document(self, did, uid):
        return self._one('teacher_documents', {'id': f'eq.{did}', 'user_id': f'eq.{uid}'})

    def documents(self, uid, limit=25, offset=0):
        return self._request('GET', 'teacher_documents', params={'user_id': f'eq.{uid}', 'select': '*', 'order': 'created_at.desc', 'limit': str(limit), 'offset': str(offset)})

    def reserve(self, record):
        return self._request('POST','rpc/reserve_teacher_document',payload={'p_record':record})[0]

    def change(self, did, uid, changes, *, status=None, task_id=None):
        filters={'id':f'eq.{did}','user_id':f'eq.{uid}'}
        if status: filters['status']=f'eq.{status}'
        if task_id: filters['task_id']=f'eq.{task_id}'
        rows=self._request('PATCH','teacher_documents',params=filters,payload=changes,prefer='return=representation')
        return rows[0] if rows else None

    def publish(self,did,uid,task,chunks):
        return self._request('POST','rpc/publish_teacher_document',payload={'p_id':did,'p_uid':uid,'p_task':task,'p_chunks':chunks})

    def search(self,uid,ids,query):
        return self._request('POST','rpc/search_teacher_passages',payload={'p_uid':uid,'p_sources':ids,'p_query':query})

    def attach(self,lid,uid,revision,ids):
        rows=self._request('POST','rpc/set_teacher_lesson_sources',payload={'p_id':lid,'p_uid':uid,'p_revision':revision,'p_sources':ids})
        return rows[0] if rows else None

    def mark_deleting(self,did,uid):
        rows=self._request('POST','rpc/mark_teacher_document_deleting',payload={'p_id':did,'p_uid':uid})
        return rows[0] if rows else None

    @contextmanager
    def storage_lock(self,uid):
        # Upload and account cleanup share this lock. Deletion is marked first,
        # so no uploader can publish a new object after cleanup has completed.
        client=redis.Redis.from_url(settings.REDIS_URL, socket_timeout=10)
        try:
            with client.lock(f'teacher-storage:{uid}',timeout=180,blocking_timeout=30):
                yield
        finally:
            client.close()

    def _storage(self,method,path,**kwargs):
        key=settings.SUPABASE_SERVICE_ROLE_KEY
        response=self.session.request(method,f'{settings.SUPABASE_URL.rstrip("/")}/storage/v1/{path}',headers={'apikey':key,'Authorization':f'Bearer {key}',**kwargs.pop('headers',{})},timeout=30,**kwargs)
        response.raise_for_status()
        return response

    def upload(self,row,data):
        with self.storage_lock(row['user_id']):
            current=self.document(row['id'],row['user_id'])
            if self.is_user_deleting(row['user_id']) or not current or current['status']!='uploading':
                raise RuntimeError('Source upload was cancelled.')
            self._storage('POST',f'object/{BUCKET}/{quote(row["object_path"],safe="/")}',data=data,headers={'Content-Type':'application/octet-stream','x-upsert':'false'})

    def download(self,row):
        response=self._storage('GET',f'object/{BUCKET}/{quote(row["object_path"],safe="/")}',stream=True)
        try:
            data=bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data)>10485760: raise ValueError('Stored document exceeds 10 MB.')
            return bytes(data)
        finally:
            response.close()

    def remove(self,row):
        self.mark_deleting(row['id'],row['user_id'])
        with self.storage_lock(row['user_id']):
            self._storage('DELETE',f'object/{BUCKET}',json={'prefixes':[row['object_path']]})
            self._request('DELETE','teacher_documents',params={'id':f'eq.{row["id"]}','user_id':f'eq.{row["user_id"]}'})

    def active_jobs(self,uid):
        return self._request('GET','teacher_documents',params={'user_id':f'eq.{uid}','status':'in.(uploading,processing)','select':'id,task_id'})

    def cancel_jobs(self,uid):
        self._request('PATCH','teacher_documents',params={'user_id':f'eq.{uid}','status':'in.(uploading,processing)'},payload={'status':'failed','error_message':'Account deletion is in progress.'})

    def delete_user_assets(self,uid):
        with self.storage_lock(uid):
            # Originals have one flat owner directory. Listing also finds orphaned
            # objects left by an interrupted upload, independent of database rows.
            while True:
                rows=self._storage('POST',f'object/list/{BUCKET}',json={'prefix':f'{uid}/','limit':1000,'offset':0}).json()
                names=[f'{uid}/{r["name"]}' for r in rows if r.get('id') and '/' not in r['name']]
                if not names: break
                self._storage('DELETE',f'object/{BUCKET}',json={'prefixes':names})
            self._request('DELETE','teacher_documents',params={'user_id':f'eq.{uid}'})

    def finish_resource(self,rid,uid,ids,content,provenance):
        rows=self._request('POST','rpc/finish_sourced_teacher_resource',payload={'p_id':rid,'p_uid':uid,'p_sources':ids,'p_content':content,'p_provenance':provenance})
        return rows[0] if rows else None

    def decorate(self,row,uid):
        if not row or not row.get('provenance'): return row
        provenance={**row['provenance'],'sources':[dict(s) for s in row['provenance'].get('sources',[])]}
        for source in provenance['sources']:
            did=source.get('document_id')
            doc=self.document(did,uid) if did else None
            source['removed']=bool(did and (not doc or doc['status']=='deleting'))
        return {**row,'provenance':provenance}


document_repository=DocumentRepository()
