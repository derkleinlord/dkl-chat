const csrf=()=>document.cookie.split('; ').find(x=>x.startsWith('dkl_csrf='))?.split('=')[1]||''
export async function api<T>(path:string, options:RequestInit={}):Promise<T>{
  const method=options.method||'GET'
  const response=await fetch(`/api${path}`,{credentials:'include',...options,headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':csrf()}:{}),...options.headers}})
  if(!response.ok){let message='Ein Fehler ist aufgetreten';try{message=(await response.json()).detail||message}catch{}throw new Error(message)}
  return response.json()
}

