import type { Provenance } from '@/lib/teacher-content'
import { copyText } from '@/lib/copy'

export function SourceReferences({provenance,language}:{provenance?:Provenance|null;language:string}){
 if(!provenance?.sources.length)return null
 const locale=language==='kk-KZ'?'kk':language==='ru-RU'?'ru':'en'
 const c=(s:string)=>copyText(s,locale)
 const location=(s:string)=>s.replace(/^Page (\d+)$/,(_,n)=>c('Page {number}').replace('{number}',n)).replace(/^Paragraph (\d+)$/,(_,n)=>c('Paragraph {number}').replace('{number}',n)).replace(/^Table (\d+), row (\d+)$/,(_,a,b)=>c('Table {number}, row {row}').replace('{number}',a).replace('{row}',b))
 return <section className="prep-source-references"><h2>{c('Source references')}</h2><p>{c('These passages supported this draft. Review the material for accuracy.')}</p><ul>{provenance.sources.map(source=><li key={source.passage_id}>{source.removed?<strong>{c('Source removed')}</strong>:<><strong>{c(source.title)}</strong> — {location(c(source.location))}</>}</li>)}</ul></section>
}
