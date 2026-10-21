const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript');
function authFor(session, refreshSession){const file=path.resolve('hooks/use-auth.ts'),m=new Module(file,module);m.paths=Module._nodeModulePaths(process.cwd());let calls=0;const original=m.require.bind(m);m.require=id=>{
 if(id==='react')return {...require('react'),useState:()=>[calls++===0?{id:'owner-a',created_at:'',email:'fictional@example.test'}:false,()=>{}],useEffect:()=>{},useCallback:fn=>fn};
 if(id==='@/lib/supabase')return {supabase:{auth:{getSession:async()=>({data:{session}}),refreshSession}}};
 if(id==='@/lib/analytics')return {};return original(id)};
 m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,file);return m.exports.useAuthState();}
test('an old workspace never obtains another account token',async()=>{assert.equal(await authFor({user:{id:'owner-b'},access_token:'other-owner-token'}).getToken(),null)});
test('the current workspace can obtain its own token',async()=>{assert.equal(await authFor({user:{id:'owner-a'},access_token:'own-token'}).getToken(),'own-token')});

test('an expiring session is refreshed before an API request',async()=>{const auth=authFor({user:{id:'owner-a'},access_token:'expired-token',expires_at:1},async()=>({data:{session:{user:{id:'owner-a'},access_token:'fresh-token'}}}));assert.equal(await auth.getToken(),'fresh-token')});
test('a refresh cannot hand an old workspace another account token',async()=>{const auth=authFor({user:{id:'owner-a'},access_token:'expired-token',expires_at:1},async()=>({data:{session:{user:{id:'owner-b'},access_token:'another-token'}}}));assert.equal(await auth.getToken(),null)});
