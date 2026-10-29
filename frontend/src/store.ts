import {create} from 'zustand'
import type {FriendRequest,Message,User} from './types'
type Chat={user:User;messages:Message[];minimized:boolean;typing:boolean;nudge:number}
type State={me:User|null;contacts:User[];requests:FriendRequest[];chats:Record<number,Chat>;setMe:(u:User|null)=>void;setContacts:(u:User[])=>void;setRequests:(r:FriendRequest[])=>void;openChat:(u:User,m:Message[])=>void;closeChat:(id:number)=>void;minimizeChat:(id:number,v:boolean)=>void;addMessage:(m:Message)=>void;setTyping:(id:number,v:boolean)=>void;nudge:(id:number)=>void;presence:(id:number,status:User['status'])=>void}
export const useStore=create<State>(set=>({
 me:null,contacts:[],requests:[],chats:{},setMe:me=>set({me}),setContacts:contacts=>set({contacts}),setRequests:requests=>set({requests}),
 openChat:(user,messages)=>set(s=>({chats:{...s.chats,[user.id]:{user,messages,minimized:false,typing:false,nudge:0}}})),
 closeChat:id=>set(s=>{const chats={...s.chats};delete chats[id];return{chats}}),minimizeChat:(id,minimized)=>set(s=>({chats:{...s.chats,[id]:{...s.chats[id],minimized}}})),
 addMessage:m=>set(s=>{const id=m.sender_id===s.me?.id?m.recipient_id:m.sender_id;const chat=s.chats[id];return chat?{chats:{...s.chats,[id]:{...chat,messages:[...chat.messages,m]}}}:{}}),
 setTyping:(id,typing)=>set(s=>s.chats[id]?{chats:{...s.chats,[id]:{...s.chats[id],typing}}}:{}),nudge:id=>set(s=>s.chats[id]?{chats:{...s.chats,[id]:{...s.chats[id],nudge:Date.now()}}}:{}),
 presence:(id,status)=>set(s=>({contacts:s.contacts.map(u=>u.id===id?{...u,status}:u),chats:Object.fromEntries(Object.entries(s.chats).map(([k,c])=>[k,c.user.id===id?{...c,user:{...c.user,status}}:c]))}))
}))

