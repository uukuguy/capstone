"""Grant published Domain Pack tools to the general executor.

The application catalog is the configuration of which packs exist. A pack is
mounted only when one of its families still has an available model. An open
model further limits the grant to that context's enabled profiles. The grant
names packs. It does not name tools, models, or endpoints.
"""

from __future__ import annotations

from collections.abc import Mapping


def checked_domain_tool_grant(value):
    if (not isinstance(value, Mapping) or set(value) != {'schema', 'profiles'}
            or value.get('schema') != 'capstone-domain-tool-grant/1'):
        raise ValueError('domain tool grant is invalid')
    profiles = value.get('profiles')
    if not isinstance(profiles, (list, tuple)) or not profiles or len(profiles) > 32:
        raise ValueError('domain tool grant is invalid')
    checked = []
    seen = set()
    for item in profiles:
        if (not isinstance(item, Mapping)
                or set(item) != {'profile_id', 'profile_version', 'implementation_family'}):
            raise ValueError('domain tool grant is invalid')
        if any(not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 128 for key in item):
            raise ValueError('domain tool grant is invalid')
        identity = (item['profile_id'], item['profile_version'], item['implementation_family'])
        if identity in seen:
            raise ValueError('domain tool grant is invalid')
        seen.add(identity)
        checked.append({key: item[key] for key in ('profile_id', 'profile_version', 'implementation_family')})
    return {'schema': 'capstone-domain-tool-grant/1', 'profiles': checked}


def domain_tool_grant(catalog, model_context=None) -> dict | None:
    """Return the packs the current configuration makes available, or None."""

    if not isinstance(catalog, Mapping):
        return None
    families = set()
    models = catalog.get('models')
    for model in models if isinstance(models, list) else []:
        if not isinstance(model, Mapping) or model.get('available') is False:
            continue
        family = model.get('implementation_family')
        if isinstance(family, str) and family.strip():
            families.add(family)
    enabled = None
    if model_context is not None:
        enabled = {(item.profile_id, item.profile_version) for item in model_context.enabled_profiles}
    selected = []
    seen = set()
    profiles = catalog.get('profiles')
    for profile in profiles if isinstance(profiles, list) else []:
        if not isinstance(profile, Mapping):
            continue
        profile_id, version = profile.get('profile_id'), profile.get('profile_version')
        published = profile.get('implementation_families')
        if (not isinstance(profile_id, str) or not isinstance(version, str)
                or not isinstance(published, list)):
            continue
        if enabled is not None and (profile_id, version) not in enabled:
            continue
        for family in published:
            if not isinstance(family, str) or family not in families:
                continue
            identity = (profile_id, version, family)
            if identity in seen or len(selected) >= 32:
                continue
            seen.add(identity)
            selected.append({
                'profile_id': profile_id, 'profile_version': version,
                'implementation_family': family})
    if not selected:
        return None
    return checked_domain_tool_grant({'schema': 'capstone-domain-tool-grant/1', 'profiles': selected})
