"""Private teacher source library, binary uploads, and revision-checked attachments."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, rate_limit_user_action
from app.api.v1.teacher import _uid, _lesson
from app.domain.teacher import StrictModel
from app.services.document_repository import document_repository
from app.services.document_worker import ingest_document
from app.services.document_text import MAX_BYTES

router=APIRouter(prefix='/teacher',tags=['teacher sources'])


class TextSource(StrictModel):
    title: str = Field(min_length=1,max_length=200)
    language: Literal['en-US','ru-RU','kk-KZ']='en-US'
    text: str = Field(min_length=1,max_length=200000)


class SourceSelection(StrictModel):
    document_ids: list[UUID] = Field(max_length=5)
    revision: int = Field(ge=1)


async def owned(did,uid):
    row=await run_in_threadpool(document_repository.document,str(did),uid)
    if not row: raise HTTPException(404,'Source not found.')
    return row


def public_document(row):
    return {key:value for key,value in row.items() if key not in ('object_path','task_id','user_id')}


def enqueue(row):
    ingest_document.apply_async(args=[row['id'],row['user_id'],row['task_id']],task_id=row['task_id'])


async def create_source(uid,title,language,kind,data):
    did,task=str(uuid4()),str(uuid4())
    record={'id':did,'user_id':uid,'title':title,'language':language,'kind':kind,'byte_count':len(data),'object_path':f'{uid}/{did}.{kind}','task_id':task}
    try:
        row=await run_in_threadpool(document_repository.reserve,record)
    except requests.HTTPError as error:
        if 'Source limit reached' in error.response.text: raise HTTPException(409,'Your library is limited to 50 sources.') from error
        raise HTTPException(409,'Could not reserve a source. Refresh and try again.') from error
    try:
        await run_in_threadpool(document_repository.upload,row,data)
        current=await run_in_threadpool(document_repository.change,did,uid,{'status':'processing'},status='uploading',task_id=task)
        if not current: raise HTTPException(409,'Source upload was cancelled.')
        await run_in_threadpool(enqueue,current)
        return public_document(current)
    except Exception as error:
        await run_in_threadpool(document_repository.change,did,uid,{'status':'failed','error_message':'Source upload or processing could not start. Retry or upload another document.'},status='uploading',task_id=task)
        await run_in_threadpool(document_repository.change,did,uid,{'status':'failed','error_message':'Source processing could not start. Retry this document.'},status='processing',task_id=task)
        if isinstance(error,HTTPException): raise
        raise HTTPException(503,'Source upload could not complete. Try again.') from error


@router.get('/documents')
async def list_documents(limit:int=Query(25,ge=1,le=50),offset:int=Query(0,ge=0),user=Depends(get_current_user)):
    uid=await _uid(user)
    rows=await run_in_threadpool(document_repository.documents,uid,limit,offset)
    return [public_document(row) for row in rows]


@router.post('/documents/text',status_code=201,dependencies=[Depends(rate_limit_user_action('teacher-source-create',10))])
async def create_text(source:TextSource,user=Depends(get_current_user)):
    return await create_source(await _uid(user),source.title,source.language,'txt',source.text.encode('utf-8'))


@router.post('/documents/upload',status_code=201,dependencies=[Depends(rate_limit_user_action('teacher-source-create',10))])
async def upload_document(file:UploadFile=File(...),language:Literal['en-US','ru-RU','kk-KZ']=Form('en-US'),user=Depends(get_current_user)):
    uid=await _uid(user)
    try:
        filename=Path((file.filename or '').replace('\\','/')).name
        kind=Path(filename).suffix.lower().lstrip('.')
        if kind not in ('pdf','docx','txt'): raise HTTPException(422,'Choose a PDF, DOCX, or UTF-8 text document.')
        data=await file.read(MAX_BYTES+1)
        if not data: raise HTTPException(422,'Choose a nonempty document up to 10 MB.')
        if len(data)>MAX_BYTES: raise HTTPException(413,'Choose a document up to 10 MB.')
        return await create_source(uid,filename[:200],language,kind,data)
    finally:
        await file.close()


@router.get('/documents/{document_id}')
async def get_document(document_id:UUID,user=Depends(get_current_user)):
    return public_document(await owned(document_id,await _uid(user)))


@router.get('/documents/{document_id}/original')
async def original(document_id:UUID,user=Depends(get_current_user)):
    row=await owned(document_id,await _uid(user))
    if row['status'] not in ('ready','failed','processing'): raise HTTPException(409,'Source is not available for download.')
    data=await run_in_threadpool(document_repository.download,row)
    return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{row["id"]}.{row["kind"]}"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@router.post('/documents/{document_id}/retry',dependencies=[Depends(rate_limit_user_action('teacher-source-retry',10))])
async def retry_document(document_id:UUID,user=Depends(get_current_user)):
    uid=await _uid(user);row=await owned(document_id,uid)
    stale=datetime.fromisoformat(row['updated_at'].replace('Z','+00:00'))<datetime.now(timezone.utc)-timedelta(minutes=3)
    if row['status']!='failed' and not (row['status'] in ('processing','uploading') and stale): raise HTTPException(409,'This source is ready or still processing.')
    task=str(uuid4())
    saved=await run_in_threadpool(document_repository.change,str(document_id),uid,{'status':'processing','error_message':None,'task_id':task},status=row['status'],task_id=row['task_id'])
    if not saved: raise HTTPException(409,'Source changed. Refresh and try again.')
    try: await run_in_threadpool(enqueue,saved)
    except Exception as error:
        await run_in_threadpool(document_repository.change,str(document_id),uid,{'status':'failed','error_message':'Source processing could not start. Retry this document.'},status='processing',task_id=task)
        raise HTTPException(503,'Source processing could not start. Retry this document.') from error
    return public_document(saved)


@router.delete('/documents/{document_id}',status_code=204)
async def delete_document(document_id:UUID,user=Depends(get_current_user)):
    row=await owned(document_id,await _uid(user))
    await run_in_threadpool(document_repository.remove,row)
    return Response(status_code=204)


@router.get('/lessons/{lesson_id}/sources')
async def lesson_sources(lesson_id:UUID,user=Depends(get_current_user)):
    uid=await _uid(user);lesson=await _lesson(lesson_id,uid)
    rows=[]
    for did in lesson.get('source_document_ids',[]):
        row=await run_in_threadpool(document_repository.document,did,uid)
        if row and row['status']=='ready': rows.append(public_document(row))
    return {'revision':lesson['revision'],'documents':rows}


@router.put('/lessons/{lesson_id}/sources')
async def attach_sources(lesson_id:UUID,selection:SourceSelection,user=Depends(get_current_user)):
    uid=await _uid(user);await _lesson(lesson_id,uid)
    ids=[str(did) for did in selection.document_ids]
    if len(set(ids))!=len(ids): raise HTTPException(422,'Select at most five distinct sources.')
    try: row=await run_in_threadpool(document_repository.attach,str(lesson_id),uid,selection.revision,ids)
    except requests.HTTPError as error: raise HTTPException(409,'Sources must be ready and belong to your account. Refresh and try again.') from error
    if not row: raise HTTPException(409,'This lesson changed. Reload before saving.')
    return row
