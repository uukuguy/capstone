import json
from jsonschema import Draft7Validator
from capstone_agent.data_gateway_mcp import argument_validation_details


def test_required_diagnostic_identifies_missing_schema_property_without_argument_values():
    schema = {'type':'object', 'properties':{'selection':{'type':'object',
        'properties':{'ref/~':{'type':'string'}},'required':['ref/~']}},'required':['selection']}
    error = next(Draft7Validator(schema).iter_errors({'selection':{},'private':'secret-canary'}))
    details = argument_validation_details(error)
    assert details == [{'path':'/selection/ref~1~0','rule':'required','actual_type':'missing'}]
    assert 'secret-canary' not in json.dumps(details)


def test_numeric_diagnostic_preserves_only_the_published_schema_bound():
    schema = {'type':'object','properties':{'count':{'type':'integer','maximum':4}}}
    error = next(Draft7Validator(schema).iter_errors({'count':123456789,'private':'secret-canary'}))
    details = argument_validation_details(error)
    assert details == [{'path':'/count','rule':'maximum','actual_type':'integer','bound':4}]
    assert '123456789' not in json.dumps(details)
    assert 'secret-canary' not in json.dumps(details)
