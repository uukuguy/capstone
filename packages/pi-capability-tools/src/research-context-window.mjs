// A model context window is a projection, never a mutation or a task deadline.
const size=value=>Array.from(JSON.stringify(value)).length;
const collections=new Set(['claims','notes','open_questions','condition_refs','cycle.pending_proposals',
  'cycle.graph.nodes','cycle.graph.actions','cycle.graph.results','cycle.graph.current_results','cycle.graph.action_contracts',
  'cycle.organization.requirements','cycle.organization.review.requirements']);
const prose=new Set(['goal','summary','scope','purpose','instruction','description','explanation','text','statement',
  'questions','expected_outputs','limitations','input_limitations','wait_reason']);

export function windowResearchContext(value,{limit,offset=0,pageSize=8}={}){
  if(offset===0&&size(value)<=limit)return structuredClone(value);
  const original=size(value);
  for(const count of [...new Set([pageSize,4,1].filter(n=>n<=pageSize))]){
    for(const textLimit of [512,128,32]){
      const pages={},clipped={fields:0,characters:0};let more=false;
      function visit(item,path='',key=''){
        if(typeof item==='string'&&prose.has(key)){
          const chars=Array.from(item);
          if(chars.length>textLimit){clipped.fields++;clipped.characters+=chars.length-textLimit;return chars.slice(0,textLimit).join('')+'…';}
        }
        if(Array.isArray(item)){
          let selected=item,start=0;
          if(collections.has(path)){
            // Small collections (notably the goal) stay visible on every page.
            start=item.length>count?offset:0;selected=item.slice(start,start+count);
            pages[path]={total:item.length,offset:start,shown:selected.length};
            if(start+count<item.length)more=true;
          }
          return selected.map((child,index)=>visit(child,path+'.'+(start+index),key));
        }
        if(item&&typeof item==='object')return Object.fromEntries(Object.entries(item).map(([name,child])=>
          [name,visit(child,path?path+'.'+name:name,name)]));
        return item;
      }
      const result=visit(value);
      result.coverage={...result.coverage,context_window:{complete:false,original_chars:original,limit_chars:limit,
        offset,page_size:count,next_offset:more?offset+count:null,collections:pages,truncated_text:clipped,
        recovery:'Read agent_research_read section="overview" with offset=next_offset and limit=page_size for remaining graph records. Exact result refs retain full findings and files. Omitted text is not absent work or evidence.'}};
      if(size(result)<=limit)return result;
    }
  }
  // Unusually large individual definitions remain in the durable graph. Keep
  // its recovery identity instead of terminating other running task nodes.
  const result={research_id:value.research_id,research_revision:value.research_revision,
    goal:Array.from(value.goal??'').slice(0,128).join(''),
    ...(value.state_scope?{state_scope:structuredClone(value.state_scope)}:{}),
    ...(value.goal_scope?{goal_scope:value.goal_scope,scope_notice:value.scope_notice}:{}),
    cycle:{checkpoint:value.cycle?.checkpoint,graph:{schema:value.cycle?.graph?.schema,
      graph_ref:value.cycle?.graph?.graph_ref,graph_revision:value.cycle?.graph?.graph_revision}},
    coverage:{context_window:{complete:false,original_chars:original,limit_chars:limit,
      recovery:'Read agent_research_read section="overview" with limit=1 and an offset for the needed graph record. Full state is retained; this window cannot authorize completion.'}}};
  return result;
}
