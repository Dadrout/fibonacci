"""Opt-in local integration check; creates and removes fictional Supabase accounts.

Requires running localhost API, frontend and worker with configured services.
Uses nonpersonal material; consumes two text generations.
"""
import os,sys,time,uuid,secrets,io,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
import requests
BASE='http://localhost:8001/api/v1';FRONT='http://localhost:3001/api/v1'
URL=settings.SUPABASE_URL.rstrip('/');KEY=settings.SUPABASE_SERVICE_ROLE_KEY
ADMIN={'apikey':KEY,'Authorization':'Bearer '+KEY}
users=[]
def req(method,url,**kwargs):
 r=requests.request(method,url,timeout=180,**kwargs)
 if r.status_code>=400: raise RuntimeError(f'{method} {url.split("?")[0]} returned {r.status_code}: '+r.text[:200])
 return r

def call(method,path,token,**kwargs):return req(method,BASE+path,headers={'Authorization':'Bearer '+token},**kwargs)
def wait(did,token,expected='ready'):
 for _ in range(40):
  row=call('GET','/teacher/documents/'+did,token).json()
  if row['status'] in ('ready','failed'):
   assert row['status']==expected,(row['status'],row.get('error_message'));return row
  time.sleep(1)
 raise RuntimeError('Worker processing timed out')
try:
 for n in range(2):
  email='rag-'+uuid.uuid4().hex+'@example.test';password=secrets.token_urlsafe(30)
  user=req('POST',URL+'/auth/v1/admin/users',headers=ADMIN,json={'email':email,'password':password,'email_confirm':True}).json();users.append(user['id'])
  token=req('POST',URL+'/auth/v1/token?grant_type=password',headers={'apikey':KEY},json={'email':email,'password':password}).json()['access_token']
  call('POST','/teacher/profile',token)
  if n==0:t1=token
  else:t2=token
 print('Temporary teacher accounts ready',flush=True)
 text='''The water cycle\n\nWater exists as solid ice, liquid water, and water vapor. The Sun supplies energy that warms liquid water and causes evaporation. Evaporation changes liquid water into water vapor.\n\nCondensation happens when water vapor cools and becomes liquid droplets. Clouds contain tiny liquid droplets or ice crystals. Precipitation is water falling from clouds as rain, snow, sleet, or hail.\n\nCollection occurs when water gathers in oceans, lakes, rivers, and puddles. Some water soaks into the ground as infiltration. Runoff flows over land into streams and rivers. Plants release water vapor through transpiration.\n\nThe cycle repeats as the Sun warms collected water. Heating favors evaporation; cooling favors condensation. Ice melts into liquid when warmed and liquid freezes into ice when cooled.'''
 data=text.encode();row=req('POST',FRONT+'/teacher/documents/upload',headers={'Authorization':'Bearer '+t1},files={'file':('fictional-water.txt',data,'text/plain')},data={'language':'en-US'}).json();did=row['id'];wait(did,t1)
 assert req('GET',FRONT+'/teacher/documents/'+did+'/original',headers={'Authorization':'Bearer '+t1}).content==data
 print('TXT upload via frontend, worker ingestion, original download passed',flush=True)
 from docx import Document
 doc=Document();doc.add_paragraph('Fictional water lesson: evaporation changes liquid into vapor.');f=io.BytesIO();doc.save(f)
 d=call('POST','/teacher/documents/upload',t1,files={'file':('water.docx',f.getvalue())}).json();wait(d['id'],t1)
 from pypdf import PdfWriter
 from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
 w=PdfWriter();p=w.add_blank_page(width=300,height=300);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')});p[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})});s=DecodedStreamObject();s.set_data(b'BT /F1 12 Tf 10 200 Td (Water vapor cools and condenses.) Tj ET');p[NameObject('/Contents')]=w._add_object(s);f=io.BytesIO();w.write(f)
 d=call('POST','/teacher/documents/upload',t1,files={'file':('water.pdf',f.getvalue())}).json();wait(d['id'],t1)
 d=call('POST','/teacher/documents/text',t1,json={'title':'Pasted example','text':'Water falls as rain.','language':'en-US'}).json();wait(d['id'],t1)
 d=call('POST','/teacher/documents/upload',t1,files={'file':('bad.pdf',b'not a PDF')}).json();wait(d['id'],t1,'failed');call('POST','/teacher/documents/'+d['id']+'/retry',t1);wait(d['id'],t1,'failed')
 print('PDF, DOCX, pasted text, malformed failure and retry passed',flush=True)
 for suffix in ('','/original'):
  assert requests.get(BASE+'/teacher/documents/'+did+suffix,headers={'Authorization':'Bearer '+t2},timeout=30).status_code==404
 assert call('GET','/teacher/documents',t2).json()==[]
 lesson=call('POST','/teacher/lessons',t1,json={'subject':'science','grade':'5','topic':'Water cycle','language':'en-US','objectives':'Explain evaporation, condensation, precipitation, and collection.'}).json();lid=lesson['id']
 other=call('POST','/teacher/lessons',t2,json={'subject':'science','grade':'5','topic':'Water cycle'}).json()
 assert requests.put(BASE+'/teacher/lessons/'+other['id']+'/sources',headers={'Authorization':'Bearer '+t2},json={'document_ids':[did],'revision':1},timeout=30).status_code==409
 lesson=call('PUT','/teacher/lessons/'+lid+'/sources',t1,json={'document_ids':[did],'revision':1}).json()
 assert requests.put(BASE+'/teacher/lessons/'+lid+'/sources',headers={'Authorization':'Bearer '+t1},json={'document_ids':[did],'revision':1},timeout=30).status_code==409
 print('Cross-account isolation and attachment revision checks passed',flush=True)
 for kind in ('quiz','flashcards'):
  rid=str(uuid.uuid4());payload={'kind':kind,'request_id':rid}
  result=call('POST','/teacher/lessons/'+lid+'/resources',t1,json=payload).json()
  assert result['status']=='ready';assert result['provenance']['sources'];assert all(s['document_id']==did for s in result['provenance']['sources'])
  assert result['lesson_snapshot']['topic']=='Water cycle'
  repeat=call('POST','/teacher/lessons/'+lid+'/resources',t1,json=payload).json();assert repeat['id']==rid
  saved=call('PATCH','/teacher/lessons/'+lid+'/resources/'+rid,t1,json={'revision':result['revision'],'content':result['content']}).json()
  assert call('GET','/teacher/lessons/'+lid+'/resources/'+rid,t1).json()['content']==saved['content']
  assert requests.get(BASE+'/teacher/lessons/'+lid+'/resources/'+rid,headers={'Authorization':'Bearer '+t2},timeout=30).status_code==404
  print(kind+' generated with Gemini, citations, duplicate prevention, save/reload passed',flush=True)
 call('DELETE','/teacher/documents/'+did,t1)
 resources=call('GET','/teacher/lessons/'+lid+'/resources',t1).json();assert all(s['removed'] for r in resources for s in r['provenance']['sources'])
 assert call('GET','/teacher/lessons/'+lid,t1).json()['source_document_ids']==[]
 print('Source deletion, detach, and retained materials with removed references passed',flush=True)
 for uid,token in zip(users,[t1,t2]):
  call('DELETE','/account',token)
  r=requests.get(URL+'/auth/v1/admin/users/'+uid,headers=ADMIN,timeout=30);assert r.status_code==404
  items=req('POST',URL+'/storage/v1/object/list/teacher-documents',headers=ADMIN,json={'prefix':uid+'/','limit':100}).json();assert not items
 print('Account deletion removed documents, storage, and Auth accounts',flush=True)
except Exception as e:
 print('CHECK FAILED: '+str(e),flush=True);raise
finally:
 for uid in users:
  # Ensure fictional test data never persists on failures.
  try:
   items=req('POST',URL+'/storage/v1/object/list/teacher-documents',headers=ADMIN,json={'prefix':uid+'/','limit':100}).json()
   names=[uid+'/'+r['name'] for r in items if r.get('id')]
   if names:req('DELETE',URL+'/storage/v1/object/teacher-documents',headers=ADMIN,json={'prefixes':names})
   requests.delete(URL+'/auth/v1/admin/users/'+uid,headers=ADMIN,timeout=30)
  except Exception: print('Fixture cleanup needs follow-up for '+uid,flush=True)
