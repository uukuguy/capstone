import pytest
from capstone_agent.thread_input import validate_submission, InputRejected

@pytest.mark.parametrize('selected',[False,True])
def test_explicit_dr_choice_is_retained_as_typed_instruction_state(selected):
    result=validate_submission({'text':'Research','deep_research':selected},mode='capstone',objects=[])
    assert result['deep_research'] is selected

@pytest.mark.parametrize('selected',['true',1,None,{}])
def test_dr_choice_rejects_non_boolean_values(selected):
    with pytest.raises((InputRejected,ValueError)):
        validate_submission({'text':'Research','deep_research':selected},mode='capstone',objects=[])

@pytest.mark.parametrize('selected',[False,True])
def test_choice_survives_command_admission_claim_and_native_context(selected):
    from types import SimpleNamespace
    from test_thread_input import idle_service, command
    from test_research_policy_compatibility import registered_binding
    from capstone_agent.native_task_context import native_context_for
    service=idle_service()
    assert service.submit_command(command(service,deep_research=selected)).status=='accepted'
    claim=service.claim_attempt('worker_test',30)
    assert claim.submission['deep_research'] is selected
    context=native_context_for(SimpleNamespace(submission=claim.submission,
        selected_task_reader=None,started_at='2026-10-27T00:00:00Z'),registered_binding('1.9.0'))
    assert context['deep_research'] is selected
