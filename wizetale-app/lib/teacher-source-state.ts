export function reconcileSelection(selection:string[], previous:string[], current:string[]):string[]{
 const key=(ids:string[])=>JSON.stringify([...ids].sort())
 return key(previous)===key(current)?selection:current
}
export function sourceRefreshLimit(loaded:number):number{return Math.min(50,Math.max(25,loaded))}
