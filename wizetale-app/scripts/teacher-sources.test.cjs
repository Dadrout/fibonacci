const test=require('node:test'), assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript');
const root=path.resolve(__dirname,'..'), cache=new Map();
function load(file){
 file=path.resolve(file);if(cache.has(file))return cache.get(file).exports;
 const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));cache.set(file,m);
 const original=m.require.bind(m);m.require=(id)=>{if(id.startsWith('@/')||id.startsWith('.')){const target=id.startsWith('@/')?path.join(root,id.slice(2)):path.resolve(path.dirname(file),id);for(const ext of ['.ts','.tsx'])if(fs.existsSync(target+ext))return load(target+ext)}return original(id)};
 m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,file);return m.exports;
}
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {ResourceDocument}=load(path.join(root,'components/teacher/resource-document.tsx'));
const content={title:'Water',instructions:'Read',objectives:[],sections:[],questions:[],flashcards:[],teacher_notes:[],answer_key:[],duration_minutes:45};
const provenance={status:'source_based',sources:[{passage_id:'1',document_id:'d',title:'Source secret title',location:'Page 3'}]};
test('source references appear only on the teacher printout',()=>{
 const props={content,kind:'quiz',language:'en-US',provenance};
 const student=renderToStaticMarkup(React.createElement(ResourceDocument,{...props,mode:'student'}));
 const teacher=renderToStaticMarkup(React.createElement(ResourceDocument,{...props,mode:'teacher'}));
 assert.ok(!student.includes('Source secret title'));assert.ok(teacher.includes('Source secret title'));assert.ok(teacher.includes('Page 3'));
});
test('removed sources do not reveal their saved title in references',()=>{
 const html=renderToStaticMarkup(React.createElement(ResourceDocument,{content,kind:'quiz',language:'ru-RU',mode:'teacher',provenance:{...provenance,sources:[{...provenance.sources[0],removed:true}]}}));
 assert.ok(html.includes('Источник удалён'));assert.ok(!html.includes('Source secret title'));
});
test('Kazakh references translate page locations',()=>{
 const html=renderToStaticMarkup(React.createElement(ResourceDocument,{content,kind:'quiz',language:'kk-KZ',mode:'teacher',provenance}));
 assert.ok(html.includes('3-бет'));
});

test('selection survives unrelated revision updates and resets for changed saved sources',()=>{
 const {reconcileSelection}=load(path.join(root,'lib/teacher-source-state.ts'));
 assert.deepEqual(reconcileSelection(['pending'],['saved'],['saved']),['pending']);
 assert.deepEqual(reconcileSelection(['pending'],['saved'],['new']),['new']);
});
test('polling refresh keeps the loaded range',()=>{
 const {sourceRefreshLimit}=load(path.join(root,'lib/teacher-source-state.ts'));
 assert.equal(sourceRefreshLimit(0),25);assert.equal(sourceRefreshLimit(50),50);
});
