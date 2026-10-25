import { readFileSync } from "node:fs";
import { configureResearchTools } from "./research-tools.mjs";
import { configureResearchGuidance } from "./research-guidance.mjs";
import {graphReferenceReadParameters} from './enterprise-graph-runtime.mjs';

function graphReadParameters(legacy) {
  // Providers require object parameters at the root. Each original handler
  // still validates its closed branch after section selects the read route.
  const parameters=structuredClone(legacy),reference=structuredClone(graphReferenceReadParameters);
  parameters.properties={...parameters.properties,...reference.properties,
    section:{...parameters.properties.section,enum:[...parameters.properties.section.enum,'reference']}};
  const required=(parameters.required??[]).filter(key=>reference.required.includes(key));
  if(required.length)parameters.required=required;else delete parameters.required;
  return parameters;
}

// Use the same tools and request guard as professional research. The task
// mirror has no controller: only the leased host worker can commit updates.
export default function (pi) {
  const config = JSON.parse(readFileSync(process.argv[2], "utf8"));
  return configureGeneralResearch(pi, config);
}

export function configureGeneralResearch(pi, config, {getControllerState,readReference} = {}) {
  if (!config.researchChannelPath) return;
  configureResearchGuidance(pi, config.researchGuidance);
  // The managed native model currently declares reasoning unsupported. Do not
  // claim that changing a label enables reasoning on this model transport.
  const research = new Proxy(pi, { get(target, key) {
    if (key === "getThinkingLevel" || key === "setThinkingLevel") return undefined;
    if(key==='registerTool'&&config.researchRuntime?.graphSchema==='capstone-enterprise-graph/2'&&readReference){
      return tool=>target.registerTool(tool.name!=='agent_research_read'?tool:{...tool,
        parameters:graphReadParameters(tool.parameters),
        description:tool.description+' For graph proposals/results, section reference with action_id reads only that exact current execute action or its selected inputs. It cannot read original uploaded sources directly. Before an execute action exists, use overview for state; assign source inspection to a delegated task with selected source_refs. Metadata is the default and lists safe logical product names, refs, roles, hashes, sizes and declared slots. The model assigns files to slots; order is not a binding. Text mode needs one exact ref, offset_bytes and length_bytes. Inspection creates no new evidence; keep the existing admitted observation refs for assessment.',
        execute:async(id,params,signal,...rest)=>{
          if(params?.section==='reference')return readReference(id,params,{signal});
          const result=await tool.execute(id,params,signal,...rest);
          if(result.details?.error?.code==='invalid_arguments'&&['action_id','ref','mode','offset_bytes','length_bytes'].some(key=>Object.hasOwn(params??{},key)))
            return {...result,content:[{type:'text',text:'Graph output inspection requires section:"reference" and action_id. For text, also provide one exact ref, mode:"text", offset_bytes and length_bytes. For state, use {section:"overview"} without reference fields. Do not repeat the mixed request.'}]};
          return result;
        }});
    }
    const value = Reflect.get(target, key);
    return typeof value === "function" ? value.bind(target) : value;
  } });
  return configureResearchTools(research, config.researchChannelPath, {
    runtimeLimits: config.runtimeLimits,
    runtimeLimitMode: config.runtimeLimitMode,
    getControllerState,
    retainedWorkBackground: true,
    boundedGraphContext: config.researchRuntime?.lightweightTaskNodes === true,
    ...(config.researchRuntime?.graphSchema === 'capstone-enterprise-graph/2' ? {
      isRecordVisible: (section, record) => section !== 'notes' ||
        !['runtime.checkpoint.','runtime.dispatch.'].some(prefix => record.note_id.startsWith(prefix)),
    } : {}),
    fatal: message => { throw new Error(message); },
  });
}
