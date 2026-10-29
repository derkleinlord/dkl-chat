export type Status='online'|'away'|'busy'|'invisible'|'offline'
export interface User{id:number;dkl_number:string;username:string;display_name:string;status:Status;status_message:string;theme:string;group_name?:string}
export interface Message{id:number;sender_id:number;recipient_id:number;body:string;created_at:string;edited_at:string|null;deleted:boolean}
export interface FriendRequest{request_id:number;user:User;created_at:string}

