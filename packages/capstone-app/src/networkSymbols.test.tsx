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
it('shows only actual kinds and the explicit boundary marker without relabelling station groups as buses',()=>{
  render(<NetworkLegend scene={{ref:'source',coordinateSystem:'schematic',displayMode:'source-regional',nodes:[{id:'s',kind:'station',label:'Station',boundary:true}],edges:[{id:'e',source:'s',target:'s',kind:'source_line'}]}}/>)
  const legend=screen.getByLabelText('拓扑符号图例')
  expect(legend.textContent).toContain('站点分组')
  expect(legend.textContent).toContain('视图边界')
  expect(legend.textContent).not.toContain('电气母线')
})
