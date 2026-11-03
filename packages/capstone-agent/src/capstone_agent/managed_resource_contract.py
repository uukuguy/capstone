"""Application-owned argument contracts, published before resource operations."""


def operation_contracts():
    text={'type':'string','minLength':1}
    def document(properties,required):
        return {'type':'object','properties':properties,'required':required,'additionalProperties':False}
    identity={'resource_id':text,'version':text}
    runtime=document({'entrypoint':{'type':'string'},'arguments':{'type':'array','maxItems':32,'items':text},
        'secret_refs':{'type':'array','maxItems':32,'items':{'type':'string','pattern':r'^secret:[A-Za-z0-9_.-]{1,128}$'}},
        'compatibility':{'type':'string'}},[])
    request=document({'kind':{'enum':['skill','mcp_local','mcp_remote']},
        'source':document({'locator':text,'revision':text},['locator','revision']),
        'subdirectory':{'type':'string'},'runtime':runtime,'dependencies':{'type':'array','items':text}},['kind','source'])
    return {
        'list':document({},[]),
        'install':document({'request_id':text,'resource_id':text,'request':request,'expected_version':text},['request_id','resource_id','request']),
        'operation':document({'request_id':text},['request_id']),
        'discover':document(identity,['resource_id','version']),
        'load_skill':document(identity,['resource_id','version']),
        'call':document({**identity,'name':text,'arguments':{'type':'object'},'catalog_revision':text},['resource_id','version','name','arguments','catalog_revision']),
        'state':document({'resource_id':text,'enabled':{'type':'boolean'},'expected_version':text},['resource_id','enabled','expected_version']),
        'uninstall':document({'resource_id':text,'expected_version':text},['resource_id','expected_version']),
        'preinstall_draft':document({'profile':text,'resource_id':text,'include':{'type':'boolean'}},['profile','resource_id','include']),
        'preinstall_export':document({'profile':text},['profile']),
        'preinstall_publish':document({'profile':text},['profile']),
        'preinstall_import':document({'manifest':{'type':'object'},'replace':{'type':'boolean'}},['manifest']),
    }
