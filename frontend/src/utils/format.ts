export const number=(n:number|null|undefined,d=2)=>n===undefined||n===null?'—':n.toLocaleString('zh-CN',{maximumFractionDigits:d,minimumFractionDigits:d});
export const edge=(n:number|null|undefined)=>n===undefined||n===null?'—':n.toLocaleString('zh-CN',{maximumFractionDigits:2});
export const percent=(n:number|null|undefined)=>n===undefined||n===null?'—':number(n*100,1)+'%';export const time=(s:string)=>new Date(s).toLocaleString('zh-CN',{hour12:false});
export const probability=(n:number|null|undefined)=>n===undefined||n===null?'—':n<.000001?n.toExponential(2):number(n,6);
