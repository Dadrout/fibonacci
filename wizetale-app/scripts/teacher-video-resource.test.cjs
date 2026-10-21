const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript');
const root=path.resolve(__dirname,'..'),cache=new Map();
function load(file){
 file=path.resolve(file);if(cache.has(file))return cache.get(file).exports;
 const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));cache.set(file,m);
 const original=m.require.bind(m);m.require=(id)=>{if(id.startsWith('@/')||id.startsWith('.')){const target=id.startsWith('@/')?path.join(root,id.slice(2)):path.resolve(path.dirname(file),id);for(const ext of ['.ts','.tsx'])if(fs.existsSync(target+ext))return load(target+ext)}return original(id)};
 m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,file);return m.exports;
}
const {isVideoResourceContent,videoResourceTitle,videoGenerationRequest,currentVideoPlaybackUrl}=load(path.join(root,'lib/teacher-content.ts'));
const lessonPage=fs.readFileSync(path.join(root,'app/teacher/lessons/[lessonId]/page.tsx'),'utf8');
const renderComponent=fs.readFileSync(path.join(root,'components/teacher/video-resource-render.tsx'),'utf8');
const content={script:{title:'Water travels',hook:'Where does rain go?',sections:[{heading:'Clouds',summary:'Water forms clouds.'}],full_narration:'Water evaporates and returns as rain.',estimated_duration_sec:180},target_duration_sec:180,voice:'female'};

test('test_video_resource_title_comes_from_script',()=>{
 assert.equal(isVideoResourceContent(content),true);
 assert.equal(videoResourceTitle(content),'Water travels');
 assert.equal(isVideoResourceContent({...content,script:{...content.script,title:4}}),false);
});

test('test_video_generation_sends_selected_duration_and_voice',()=>{
 assert.deepEqual(videoGenerationRequest('request-1',240,'male'),{
  kind:'video',request_id:'request-1',target_duration_sec:240,voice:'male',
 });
});

test('test_video_render_is_hidden_after_script_revision_changes',()=>{
 const render={id:'render-1',status:'ready',resource_revision:3,video_url:'https://media.example/video.mp4'};
 assert.equal(currentVideoPlaybackUrl(render,3),render.video_url);
 assert.equal(currentVideoPlaybackUrl(render,4),null);
 assert.equal(currentVideoPlaybackUrl({...render,status:'processing'},3),null);
});

test('video render state stays with its lesson resource and stale requests are ignored',()=>{
 assert.match(lessonPage,/<VideoResourceRender\s+key=\{`\$\{lessonId\}:\$\{selected\.id\}`\}/);
 assert.match(renderComponent,/identityRef\.current\s*=\s*identity/);
 assert.match(renderComponent,/requestIdentity\s*!==\s*identityRef\.current/);
});

test('video status polling schedules another attempt after a transient failure',()=>{
 assert.match(renderComponent,/pollRetry/);
 assert.match(renderComponent,/catch\(\(\)\s*=>\s*\{[\s\S]*?setPollRetry/);
});
