import {expect,it} from 'vitest'
import {render,screen} from '@testing-library/react'
import {networkSymbol} from './networkSymbols'
import NetworkLegend from './NetworkLegend'
import {sceneFrame} from './networkScene.worker'
import {buildSceneIndex} from './networkSceneIndex'
it('maps published station/equipment kinds to explicit neutral class glyphs',()=>{
  const kinds=['station','busbars','transformers','breakers','disconnectors','ground_disconnectors','windings','terminal','voltage_level','connection_node','line']
  const symbols=kinds.map(kind=>networkSymbol(kind))
  expect(new Set(symbols.map(symbol=>symbol.code)).size).toBe(kinds.length)
  expect(networkSymbol('busbars').label).toContain('母线条')
  expect(networkSymbol('breakers').label).toContain('断路器')
  expect(networkSymbol('ground_disconnectors').label).toContain('接地')
  const index=buildSceneIndex({ref:'station',coordinateSystem:'schematic',displayMode:'source-detail',nodes:kinds.map((kind,i)=>({id:`node${i}`,label:kind,kind,x:i,y:i%3})),edges:[]})
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,focusIds:[]})
  const actualCodes=Array.from({length:frame.points.length/8},(_,i)=>frame.points[i*8+3])
  expect(new Set(actualCodes)).toEqual(new Set(symbols.map(symbol=>symbol.code)))
})
it('uses purpose glyphs for generators, loads, and three-winding transformers',()=>{
  const generator=networkSymbol('generator'),load=networkSymbol('load')
  expect(generator.code).not.toBe(load.code)
  expect(generator.label).toMatch(/发电机|generator/i)
  expect(load.label).toMatch(/负荷|load/i)
  expect(networkSymbol('trafo').code).toBe(networkSymbol('transformer').code)
  expect(networkSymbol('trafo3w').code).not.toBe(networkSymbol('trafo').code)
})
it('keeps source switches neutral unless the source gives an explicit state',()=>{
  for(const kind of ['breakers','disconnectors','switch','ground_disconnectors']){
    const unknown=networkSymbol(kind)
    expect(unknown.label).toMatch(/未知|未核验/)
    expect(networkSymbol(kind,'unknown').code).toBe(unknown.code)
    expect(networkSymbol(kind,'open').code).not.toBe(unknown.code)
    expect(networkSymbol(kind,'closed').code).not.toBe(unknown.code)
    expect(networkSymbol(kind,'open').label).toMatch(/分位|open/i)
    expect(networkSymbol(kind,'closed').label).toMatch(/合位|closed/i)
  }
})
it('shows only actual kinds and the explicit boundary marker without relabelling station groups as buses',()=>{
  render(<NetworkLegend scene={{ref:'source',coordinateSystem:'schematic',displayMode:'source-regional',nodes:[{id:'s',kind:'station',label:'Station',boundary:true}],edges:[{id:'e',source:'s',target:'s',kind:'source_line'}]}}/>)
  const legend=screen.getByLabelText('拓扑符号图例')
  expect(legend.textContent).toContain('站点分组')
  expect(legend.textContent).toContain('视图边界')
  expect(legend.textContent).not.toContain('电气母线')
})
