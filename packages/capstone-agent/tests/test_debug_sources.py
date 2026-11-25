import json

from capstone_agent.debug_sources import resolve_sources


def test_source_selection_follows_revision_not_instance_or_package_version(tmp_path):
    entries = [{'repository':'data-gateway','revision': revision} for revision in ['a'*64,'b'*64]]
    (tmp_path/'manifest.json').write_text(json.dumps({'sources':entries}))
    instance = {'instance_id':'same','server_version':'1.1.0'}
    publication = {'available':True,'catalog':{'instance':instance}}
    assert resolve_sources(publication,tmp_path)['status']=='unreported'
    for entry in entries:
        instance['source_sha256']=entry['revision']
        assert resolve_sources(publication,tmp_path)['selected']==entry
    instance['source_sha256']='0'*64
    assert resolve_sources(publication,tmp_path)['status']=='source_missing'
    assert resolve_sources({'available':False},tmp_path)['selected'] is None


def test_new_gateway_release_can_arrive_after_image_without_restart(tmp_path):
    image,library=tmp_path/'image',tmp_path/'library'
    image.mkdir()
    digest='d'*64
    pub={'available':True,'catalog':{'instance':{'source_sha256':digest}}}
    assert resolve_sources(pub,image,library)['status']=='source_missing'
    release=library/digest
    release.mkdir(parents=True)
    archive=f'data-gateway-{digest}.zip'
    row={'repository':'data-gateway','revision':digest,'archive':archive}
    (release/'manifest.json').write_text(json.dumps({'sources':[row]}))
    assert resolve_sources(pub,image,library)['status']=='source_missing'
    (release/archive).touch()
    assert resolve_sources(pub,image,library)['selected']==row
