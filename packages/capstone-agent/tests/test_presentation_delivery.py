from capstone_agent.native_product_roles import PresentationDeliveries


def start(call='render',source='slides.json',pdf=True):
    return {'type':'tool_execution_start','toolName':'agent_presentations','toolCallId':call,
        'args':{'operation':'render','document':{'spec':source,'output':'out.pptx','pdf':pdf}}}


def end(call='render',failed=False,pdf=True):
    return {'type':'tool_execution_end','toolName':'agent_presentations','toolCallId':call,'isError':failed,
        'result':{'details':{'capability':'agent_presentations','ok':not failed,'result':{
            'schema':'capstone-presentation-library-render/1','output':'out.pptx','output_sha256':'a'*64,
            'pdf':{'status':'ready' if pdf else 'failed','path':'out.pdf','sha256':'b'*64}}}}}


def artifacts(pdf=True):
    return [{'metadata':{'path':'out.pptx','sha256':'a'*64}},
        *([{'metadata':{'path':'out.pdf','sha256':'b'*64}}] if pdf else [])]


def test_failed_render_and_success_claim_without_saved_bytes_cannot_complete():
    for failed in (False,True):
        state=PresentationDeliveries();state.observe(start());state.observe(end(failed=failed))
        assert not state.confirmed([])


def test_requested_pdf_is_required_but_explicit_pptx_only_is_valid():
    state=PresentationDeliveries();state.observe(start());state.observe(end(pdf=False))
    assert not state.confirmed(artifacts(False))
    state=PresentationDeliveries();state.observe(start(pdf=False));state.observe(end(pdf=False))
    assert state.confirmed(artifacts(False))


def test_successful_repair_supersedes_failure_for_same_content_and_checks_hashes():
    state=PresentationDeliveries();state.observe(start('bad'));state.observe(end('bad',failed=True))
    state.observe(start('fixed'));state.observe(end('fixed'))
    assert state.confirmed(artifacts())
    changed=artifacts();changed[0]['metadata']['sha256']='c'*64
    assert not state.confirmed(changed)


def test_unrelated_tool_error_has_no_product_requirement():
    state=PresentationDeliveries();state.observe({'type':'tool_execution_end','toolName':'read','isError':True})
    assert state.confirmed([])
