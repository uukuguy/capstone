import type {ThreadMessageLike} from '@assistant-ui/react'
import type {EventEnvelope} from './threadProtocol'

export type InstructionProductScope={attemptId:string;number:number;text:string}
export const instructionProductLabel=(scope:InstructionProductScope)=>`指令 ${String(scope.number).padStart(2,'0')}`

export function instructionProductScopesFromEvents(events:readonly EventEnvelope[]) {
  const scopes=new Map<string,InstructionProductScope>()
  for(const event of [...events].sort((a,b)=>a.eventSeq-b.eventSeq)){
    if(event.eventType!=='command_accepted'||!event.attemptId||scopes.has(event.attemptId)
      ||!['send_auto','send_message','send_ordinary','send_professional'].includes(String(event.payload.kind)))continue
    const nested=event.payload.payload as Record<string,unknown>|undefined
    const text=typeof event.payload.text==='string'?event.payload.text:typeof nested?.text==='string'?nested.text:''
    if(text)scopes.set(event.attemptId,{attemptId:event.attemptId,number:scopes.size+1,text})
  }
  return scopes
}

/** Use the complete persisted conversation, not the visible/folded message list. */
export function instructionProductScopes(messages:readonly ThreadMessageLike[]) {
  const scopes=new Map<string,InstructionProductScope>()
  for(const message of messages){
    if(message.role!=='user')continue
    const attemptId=message.metadata?.custom?.attemptId
    if(typeof attemptId!=='string'||scopes.has(attemptId))continue
    const text=typeof message.content==='string'?message.content:message.content.filter(part=>part.type==='text').map(part=>part.text).join('\n')
    scopes.set(attemptId,{attemptId,number:scopes.size+1,text})
  }
  return scopes
}
