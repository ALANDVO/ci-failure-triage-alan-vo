let csrf='';
export function setCsrf(value:string){csrf=value;}
export async function request<T>(url:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch(url,{method,credentials:'include',headers:{'Content-Type':'application/json',...(method==='GET'?{}:{'X-CSRF-Token':csrf})},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok){let message=`Request failed (${response.status})`;try{const data=await response.json();message=data.error?.message||JSON.stringify(data.detail)||message;}catch{}throw new Error(message);}
 return response.status===204?undefined as T:response.json();
}
export function query(repository:string,branch:string,minutes:number){return new URLSearchParams({repository,branch,investigation_minutes:String(minutes)}).toString();}
export async function download(url:string){
 const response=await fetch(url,{credentials:'include'});if(!response.ok)throw new Error('Export failed; check your session and filters');
 const blob=await response.blob();const link=document.createElement('a');link.href=URL.createObjectURL(blob);
 link.download=response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1]||'ci-report';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
}
