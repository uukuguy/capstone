import {describe,expect,it} from 'vitest'
import {buildSceneIndex,queryScene,pickScene,searchScene} from './networkSceneIndex'
import {formalNetworkScene,type NetworkScene} from './networkScene'
const scene:NetworkScene={ref:'test',coordinateSystem:'schematic',nodes:[
  {id:'a',kind:'station',label:'Alpha',x:0,y:0},{id:'b',kind:'bus',label:'Beta',x:100,y:0},{id:'c',kind:'source_node',label:'Far',x:1000,y:600}],
  edges:[{id:'one',source:'a',target:'b',kind:'line'},{id:'two',source:'a',target:'b',kind:'line'}]}
describe('indexed network scenes',()=>{
  it('preserves typed objects and parallel edge identities with separate routes',()=>{
    const index=buildSceneIndex(scene)
    expect(index.scene.nodes[0].kind).toBe('station')
    expect(index.edgeOffsets[0]).not.toBe(index.edgeOffsets[1])
    expect(index.scene.edges.map(edge=>edge.id)).toEqual(['one','two'])
  })
  it('culls outside geometry, includes crossing edges and bounds output independently of total size',()=>{
    const index=buildSceneIndex(scene)
    const viewport=queryScene(index,{x:0,y:-20,width:150,height:80},1,1)
    expect(viewport.nodeIndices.length).toBeLessThanOrEqual(1)
    expect(viewport.edgeIndices.length).toBe(1)
    expect(viewport.limited).toBe(true)
    expect([...viewport.nodeIndices]).not.toContain(2)
  })
  it('picks by spatial position and searches stable IDs without an unbounded result list',()=>{
    const index=buildSceneIndex(scene)
    const x=index.positions[0],y=index.positions[1]
    expect(pickScene(index,x,y,10)?.id).toBe('a')
    expect(searchScene(index,'beta',1)).toEqual([{id:'b',label:'Beta',kind:'bus',type:'node'}])
    expect(searchScene(index,'',1)).toEqual([])
  })
  it('picks parallel circuit routes independently rather than their shared center line',()=>{
    const index=buildSceneIndex(scene),x=(index.positions[0]+index.positions[2])/2,y=(index.positions[1]+index.positions[3])/2
    expect(pickScene(index,x,y+index.edgeOffsets[0],1)?.id).toBe('one')
    expect(pickScene(index,x,y+index.edgeOffsets[1],1)?.id).toBe('two')
  })
  it('adapts electrical diagrams without turning source stations into buses',()=>{
    const adapted=formalNetworkScene({schema:'capstone-network-diagram/1.0',model:{id:'m',revision:'1',source:'authority'},coordinate_system:'schematic',fingerprint:'f',ref:'d',buses:[{id:'bus',label:'Bus',x:null,y:null,vn_kv:330}],branches:[]})
    expect(adapted.nodes[0]).toMatchObject({id:'bus',kind:'bus',voltageKv:330})
  })
  it('preserves admitted quantitative overlays and explicit disconnected state in the large-scene adapter',()=>{
    const diagram={schema:'capstone-network-diagram/1.0' as const,model:{id:'m',revision:'1',source:'authority'},coordinate_system:'schematic' as const,fingerprint:'f',ref:'d',buses:[{id:'bus',label:'Bus',x:null,y:null,vn_kv:330}],branches:[],disconnections:[]}
    const adapted=formalNetworkScene(diagram,{overlay:{metric:'voltage_pu',unit:'p.u.',source_ref:'evidence',values:[{id:'bus',value:.97}]},annotations:{scene:{label:'case',context_ref:'c',model_revision:'1',source_ref:'evidence'},states:[{label:'unknown',style:'unresolved',ids:['bus'],source_ref:'evidence'}],regions:[]}})
    expect(adapted.nodes[0].color).toBeTruthy()
    expect(adapted.nodes[0].state).toBe('unresolved')
    expect(adapted.nodes[0].details).toContainEqual({label:'voltage_pu',value:'0.97 p.u.'})
  })
})
