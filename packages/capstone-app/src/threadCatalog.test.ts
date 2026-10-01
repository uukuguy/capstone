import { describe, expect, it } from 'vitest'
import { parseThreadCatalog } from './threadCatalog'

describe('thread catalog protocol', () => {
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
})
