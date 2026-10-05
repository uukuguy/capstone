import { describe, expect, it } from 'vitest'
import { isLikelyNaturalLanguageModelRequest, parseThreadCatalog, resolveThreadModelReference, resolveThreadModelCommandReference } from './threadCatalog'

describe('thread catalog protocol', () => {
  it('preserves registered uppercase canonical model IDs', () => {
    const catalog = parseThreadCatalog({ schema: 'capstone-thread-catalog/1', profiles: [], models: [{ model_id: 'GBnetwork', authority_model_ref: 'gridctl:GBnetwork', display_name: 'GBnetwork', diagram_provider_id: 'pandapower', implementation_family: 'pandapower' }] })
    expect(resolveThreadModelReference(catalog, 'GBnetwork 电网模型')).toMatchObject({ kind: 'resolved', model: { modelId: 'GBnetwork' } })
  })
  it('parses bounded model and profile selector metadata', () => {
    const catalog = parseThreadCatalog({
      schema: 'capstone-thread-catalog/1',
      models: [{
        model_id: 'ieee39', authority_model_ref: 'gridctl:ieee39',
        display_name: 'IEEE-39', diagram_provider_id: 'pandapower',
        implementation_family: 'pandapower',
      }],
      profiles: [{
        profile_id: 'pandapower-static-analysis', profile_version: '1.0.1',
        display_name: 'Pandapower Static Analysis', implementation_families: ['pandapower'],
      }],
    })

    expect(catalog.models[0]).toMatchObject({ modelId: 'ieee39', displayName: 'IEEE-39' })
    expect(catalog.profiles[0]).toMatchObject({ profileId: 'pandapower-static-analysis', profileVersion: '1.0.1' })
  })

  it('rejects unknown fields instead of accepting unbounded selector data', () => {
    expect(() => parseThreadCatalog({
      schema: 'capstone-thread-catalog/1', models: [], profiles: [], private_authority_object: {},
    })).toThrow('unknown field')
  })

  it('resolves exact IDs, unique namespaced suffixes, and display names without guessing ambiguous references', () => {
    const catalog = parseThreadCatalog({
      schema: 'capstone-thread-catalog/1',
      models: [
        { model_id: 'ieee39', authority_model_ref: 'gridctl:ieee39', display_name: 'IEEE-39', diagram_provider_id: 'pandapower', implementation_family: 'pandapower' },
        { model_id: 'pypsa-example/model_energy', authority_model_ref: 'pypsa:model_energy', display_name: 'Model-Energy', diagram_provider_id: 'pypsa', implementation_family: 'pypsa' },
        { model_id: 'pypsa-example/two-bus', authority_model_ref: 'pypsa:two-bus', display_name: 'Two Bus', diagram_provider_id: 'pypsa', implementation_family: 'pypsa' },
        { model_id: 'pypsa-example/other-two-bus', authority_model_ref: 'pypsa:other-two-bus', display_name: 'Two Bus', diagram_provider_id: 'pypsa', implementation_family: 'pypsa' },
      ],
      profiles: [],
    })

    expect(resolveThreadModelReference(catalog, 'pypsa-example/model_energy')).toMatchObject({ kind: 'resolved', model: { modelId: 'pypsa-example/model_energy' }, matchedBy: 'exact' })
    expect(resolveThreadModelReference(catalog, 'model_energy')).toMatchObject({ kind: 'resolved', model: { modelId: 'pypsa-example/model_energy' }, matchedBy: 'suffix' })
    expect(resolveThreadModelReference(catalog, 'IEEE-39')).toMatchObject({ kind: 'resolved', model: { modelId: 'ieee39' }, matchedBy: 'display_name' })
    expect(resolveThreadModelReference(catalog, 'Two Bus')).toMatchObject({ kind: 'ambiguous', candidates: [{ modelId: 'pypsa-example/other-two-bus' }, { modelId: 'pypsa-example/two-bus' }] })
    expect(resolveThreadModelReference(catalog, 'missing-model')).toEqual({ kind: 'unknown', reference: 'missing-model' })
  })

  it('distinguishes short unknown controls from longer analytical requests independent of language', () => {
    expect(isLikelyNaturalLanguageModelRequest('不存在模型')).toBe(false)
    expect(isLikelyNaturalLanguageModelRequest('IEEE-39 network and analyze line 11')).toBe(true)
    expect(isLikelyNaturalLanguageModelRequest('IEEE-39 网络并解析线路 11')).toBe(true)
  })

  it('resolves a registered model with a Chinese suffix without accepting an arbitrary compound', () => {
    const catalog = { models: [{ modelId: 'case24_ieee_rts', authorityModelRef: 'gridctl:case24_ieee_rts', displayName: 'RTS-24', diagramProviderId: 'pandapower', implementationFamily: 'pandapower' }], profiles: [] }
    for (const reference of ['case24_ieee_rts 电网模型', 'case24_ieee_rts网络', 'RTS-24 网络模型']) {
      expect(resolveThreadModelReference(catalog, reference)).toMatchObject({ kind: 'resolved', model: { modelId: 'case24_ieee_rts' } })
    }
    expect(resolveThreadModelReference(catalog, 'case24_ieee_rts 电网模型并执行潮流')).toMatchObject({ kind: 'unknown' })
    expect(resolveThreadModelCommandReference(catalog, 'case24_ieee_rts 电网模型并执行潮流')).toMatchObject({ kind: 'resolved', model: { modelId: 'case24_ieee_rts' } })
    expect(resolveThreadModelCommandReference(catalog, 'case24_ieee_rts_backup 并执行潮流')).toMatchObject({ kind: 'unknown' })
    expect(resolveThreadModelCommandReference(catalog, 'case24_ieee_rts arbitrary compound')).toMatchObject({ kind: 'unknown' })
    const other = { ...catalog.models[0], modelId: 'ieee39', displayName: 'IEEE-39' }
    expect(resolveThreadModelCommandReference({ ...catalog, models: [...catalog.models, other] }, 'case24_ieee_rts 电网模型并打开 IEEE-39')).toMatchObject({ kind: 'ambiguous' })
  })
})
