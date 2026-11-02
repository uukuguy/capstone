import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {NetworkView} from './NetworkView'
import type {NetworkScene} from './networkScene'
import {sampleDiagramView} from './networkFixture'
const captured=vi.hoisted(()=>vi.fn())
afterEach(()=>{cleanup();captured.mockClear()})
vi.mock('./networkLayout',()=>({layoutNetwork:()=>{throw new Error('Legacy synchronous layout must not run for large networks')},usesModelCoordinates:()=>{throw new Error('Legacy coordinates must not run for large networks')}}))
vi.mock('./LargeNetworkView',()=>({default:(props:{scene:NetworkScene;focusIds:string[]})=>{captured(props);return <div aria-label="large-dispatch">{props.scene.nodes.length}:{props.scene.nodes[0].kind}:{props.focusIds.join(',')}</div>}}))
it('dispatches large formal diagrams before any legacy layout and preserves task focus',()=>{
  const diagram={schema:'capstone-network-diagram/1.0' as const,model:{id:'large',revision:'1',source:'authority'},coordinate_system:'schematic' as const,fingerprint:'f',ref:'d',buses:Array.from({length:1200},(_,i)=>({id:`bus${i}`,label:`Bus ${i}`,x:null,y:null,vn_kv:330})),branches:[]}
  render(<NetworkView view={{schema:'capstone-network-view/2.0',ordinal:1,diagram,layer:{schema:'capstone-network-layer/1.0',ordinal:1,diagram_ref:'d',model_revision:'1',focus_ids:['bus10'],next_focus_ids:[],overlay:null}}} modelName="Large" focusKey="task"/>)
  expect(screen.getByLabelText('large-dispatch').textContent).toBe('1200:bus:bus10')
})
it('preserves annotation-derived fault attention, source-specific camera keys and history across the threshold',()=>{
  const view=structuredClone(sampleDiagramView)
  view.diagram.buses.push(...Array.from({length:1100},(_,i)=>({id:`extra${i}`,label:`Extra ${i}`,x:null,y:null,vn_kv:330})))
  const edge=view.diagram.branches[0].id,old=view.diagram.buses[0].id
  view.layer.focus_ids=[]
  view.layer.annotations={scene:{label:'Fault',context_ref:'context',model_revision:view.diagram.model.revision,source_ref:'accepted-scene'},states:[{label:'Disconnected',style:'disconnected',ids:[edge],source_ref:'evidence'}],regions:[]}
  render(<NetworkView view={view} modelName="Fault" focusKey="attempt" cameraViewKey="saved" historyFocusIds={[old]} returnTaskRequest={1}/>)
  const props=captured.mock.calls.at(-1)![0]
  expect(props.focusIds).toContain(edge)
  expect(props.viewKey).toBe('saved:attention:accepted-scene')
  expect(props.taskLayerReady).toBe(true)
  expect(props.scene.nodes.find((node:{id:string})=>node.id===old).color).toEqual([.52,.65,.62])
})
