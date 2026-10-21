const test=require('node:test'), assert=require('node:assert/strict');
const fs=require('node:fs'), path=require('node:path'), Module=require('node:module'), ts=require('typescript');
const sourcePath=path.resolve(__dirname,'../lib/backend-proxy.ts');
const compiled=ts.transpileModule(fs.readFileSync(sourcePath,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const loaded=new Module(sourcePath,module);loaded.filename=sourcePath;loaded.paths=Module._nodeModulePaths(path.dirname(sourcePath));loaded._compile(compiled,sourcePath);
const {proxyBackend}=loaded.exports;
test('topic-video downloads preserve every binary byte through the frontend proxy',async()=>{
 const previousFetch=global.fetch,previousUrl=process.env.BACKEND_API_URL;
 process.env.BACKEND_API_URL='https://backend.example.test';
 const bytes=new Uint8Array([0,255,128,1,254,10,13,0]);
 global.fetch=async()=>new Response(bytes,{headers:{'Content-Type':'video/mp4','Content-Disposition':'attachment; filename="topic.mp4"'}});
 try {
  const response=await proxyBackend({headers:new Headers({Authorization:'Bearer test'})},'teacher/video-renders/test/video','GET');
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()),bytes);
  assert.equal(response.headers.get('Content-Type'),'video/mp4');
  assert.equal(response.headers.get('Content-Disposition'),'attachment; filename="topic.mp4"');
 }finally{global.fetch=previousFetch;if(previousUrl===undefined)delete process.env.BACKEND_API_URL;else process.env.BACKEND_API_URL=previousUrl}
});

test('rate limits preserve Retry-After through JSON and upload proxies',async()=>{
 const previousFetch=global.fetch,previousUrl=process.env.BACKEND_API_URL;
 process.env.BACKEND_API_URL='https://backend.example.test';
 global.fetch=async()=>Response.json({detail:'Rate limit exceeded.'},{status:429,headers:{'Retry-After':'37'}});
 try {
  const response=await proxyBackend({headers:new Headers({Authorization:'Bearer test'}),text:async()=>''},'teacher/profile','POST');
  assert.equal(response.status,429);assert.equal(response.headers.get('Retry-After'),'37');
  const upload=await loaded.exports.proxyTeacherUpload(new Request('https://app.example.test/upload',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'multipart/form-data; boundary=test'},body:new Uint8Array([0,255])}));
  assert.equal(upload.status,429);assert.equal(upload.headers.get('Retry-After'),'37');
 }finally{global.fetch=previousFetch;if(previousUrl===undefined)delete process.env.BACKEND_API_URL;else process.env.BACKEND_API_URL=previousUrl}
});
test('successful resource deletion remains 204 through the frontend proxy', async()=>{
 const previousFetch=global.fetch, previousUrl=process.env.BACKEND_API_URL;
 process.env.BACKEND_API_URL='https://backend.example.test';global.fetch=async()=>new Response(null,{status:204});
 try {const response=await proxyBackend({headers:new Headers({Authorization:'Bearer test'}),text:async()=>''},'teacher/lessons/test','DELETE');assert.equal(response.status,204);assert.equal(await response.text(),'');}
 finally{global.fetch=previousFetch;if(previousUrl===undefined)delete process.env.BACKEND_API_URL;else process.env.BACKEND_API_URL=previousUrl}
});

test('multipart uploads keep their boundary and binary file bytes',async()=>{
 assert.equal(typeof loaded.exports.proxyTeacherUpload,'function');
 const old=global.fetch, url=process.env.BACKEND_API_URL;process.env.BACKEND_API_URL='https://backend.example.test';
 const bytes=new Uint8Array([0,255,3,128]);let forwarded;
 global.fetch=async(_url,options)=>{forwarded=options;return Response.json({id:'source'},{status:201})};
 try {
  const request=new Request('https://app.example.test/upload',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'multipart/form-data; boundary=test'},body:bytes});
  const response=await loaded.exports.proxyTeacherUpload(request);
  assert.equal(response.status,201);assert.equal(forwarded.headers['Content-Type'],'multipart/form-data; boundary=test');assert.deepEqual(new Uint8Array(forwarded.body),bytes);
 }finally{global.fetch=old;if(url===undefined)delete process.env.BACKEND_API_URL;else process.env.BACKEND_API_URL=url}
});

test('oversized uploads are rejected before reading the body',async()=>{
 assert.equal(typeof loaded.exports.proxyTeacherUpload,'function');
 const response=await loaded.exports.proxyTeacherUpload({headers:new Headers({Authorization:'Bearer test','Content-Type':'multipart/form-data; boundary=test','Content-Length':String(12*1024*1024)}),body:{getReader(){throw Error('Must not read oversized body')}}});
 assert.equal(response.status,413);
});
