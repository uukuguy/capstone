import {applicationCapacity} from './applicationCapacity'

/** Aggregate source-byte reservations across all instruction attachment views. */
export class AttachmentMemory {
  private used=0
  constructor(private limit:()=>number){}
  reserve(bytes:number):()=>void {
    if(!Number.isSafeInteger(bytes)||bytes<0)throw new Error('附件大小无效。')
    if(bytes>this.limit()-this.used)throw new Error('同时读取的附件较多，请收起其他附件预览后重试。')
    this.used+=bytes
    let active=true
    return ()=>{if(active){active=false;this.used-=bytes}}
  }
}

export const attachmentMemory=new AttachmentMemory(()=>applicationCapacity('attachment_buffer_bytes'))
