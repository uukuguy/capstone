/** Persist receipts only. Local file bytes and credentials never enter browser storage. */
export type UploadResume = {requestId:string;uploadId?:string;name:string;size:number;modified:number}
export function resumeKey(threadId:string){return `capstone.resource-upload.${threadId}`}
export function readUploadResume(threadId:string):UploadResume|undefined {
  try {
    const value=JSON.parse(localStorage.getItem(resumeKey(threadId))||'null')
    if(value&&typeof value.requestId==='string'&&typeof value.name==='string'
      &&Number.isSafeInteger(value.size)&&value.size>0&&typeof value.modified==='number'
      &&(value.uploadId===undefined||/^upload_[a-f0-9]{32}$/.test(value.uploadId)))return value
  }catch{/* Storage may be unavailable. The live transfer can still proceed. */}
}
export function saveUploadResume(threadId:string,value?:UploadResume){
  try{if(value)localStorage.setItem(resumeKey(threadId),JSON.stringify(value));else localStorage.removeItem(resumeKey(threadId))}catch{/* Keep the in-memory receipt. */}
}
