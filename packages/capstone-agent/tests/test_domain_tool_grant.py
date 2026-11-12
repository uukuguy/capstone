from capstone_agent.domain_tool_grant import domain_tool_grant


def catalog(*families, available=True):
    return {
        'models': [{
            'model_id': family + '-case', 'implementation_family': family, 'available': available,
        } for family in families],
        'profiles': [{
            'profile_id': family + '-pack', 'profile_version': '1.0.0', 'implementation_families': [family],
        } for family in families],
    }


def test_available_pack_is_granted_and_an_unavailable_pack_is_not():
    grant = domain_tool_grant(catalog('pandapower', 'pypsa'))
    assert [item['implementation_family'] for item in grant['profiles']] == ['pandapower', 'pypsa']
    assert domain_tool_grant(catalog('pandapower', available=False)) is None


def test_open_model_uses_only_its_enabled_profiles():
    class Profile:
        def __init__(self, profile_id):
            self.profile_id = profile_id
            self.profile_version = '1.0.0'

    class Context:
        enabled_profiles = (Profile('pandapower-pack'),)

    grant = domain_tool_grant(catalog('pandapower', 'pypsa'), Context())
    assert grant['profiles'] == [{
        'profile_id': 'pandapower-pack', 'profile_version': '1.0.0',
        'implementation_family': 'pandapower'}]
    class Snapshot:
        enabled_profiles = (('pandapower-pack', '1.0.0'),)
    assert domain_tool_grant(catalog('pandapower', 'pypsa'), Snapshot()) == grant
