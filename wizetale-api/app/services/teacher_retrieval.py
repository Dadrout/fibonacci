"""Bounded keyword retrieval and validated resource-level source references."""
import logging
import re
from time import monotonic
from typing import Literal
from pydantic import Field
from app.domain.teacher import StrictModel, ResourceContent

logger=logging.getLogger(__name__)


class InsufficientSources(ValueError):
    def __init__(self):
        super().__init__('The selected sources do not provide enough information. Add relevant material or change the lesson topic.')


class GroundedResource(StrictModel):
    sufficient: bool
    content: ResourceContent | None
    passage_ids: list[str] = Field(max_length=8)


def build_context(lesson,uid,repository):
    started=monotonic()
    ids=lesson.get('source_document_ids',[])
    if not ids: return []
    query=' OR '.join(dict.fromkeys(re.findall(r'[^\W_]+', lesson['topic']+' '+lesson.get('objectives',''),re.UNICODE)))[:4000]
    passages=[]
    pasted=lesson.get('source_material','').strip()
    if pasted:
        passages.append({'passage_id':'lesson-source','document_id':None,'title':'Lesson source material','location':'Lesson details','text':pasted[:8000]})
    for row in repository.search(uid,ids,query):
        budget=16000-sum(len(p['text']) for p in passages)
        if budget<=0 or len(passages)>=8: break
        passages.append({'passage_id':str(row['id']),'document_id':str(row['document_id']),'title':row['title'],'location':row['location'],'text':row['body'][:budget]})
    logger.info('teacher_retrieval passages=%d context_characters=%d latency_ms=%d',len(passages),sum(len(p['text']) for p in passages),int((monotonic()-started)*1000))
    if not passages: raise InsufficientSources()
    return passages


def validate_grounded(response,passages):
    allowed={p['passage_id']:p for p in passages}
    if not response.sufficient or not response.content or not response.passage_ids or any(pid not in allowed for pid in response.passage_ids):
        raise InsufficientSources()
    sources=[{key:allowed[pid][key] for key in ('passage_id','document_id','title','location')} for pid in dict.fromkeys(response.passage_ids)]
    return response.content, {'status':'source_based','sources':sources}
