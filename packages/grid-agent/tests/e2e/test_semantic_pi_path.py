from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from grid_agent.contracts import AnswerEnvelope
from grid_agent.runtime.lock import PiRuntimeLock


ROOT = Path(__file__).resolve().parents[4]


def test_scripted_pi_non_blocking_audit_keeps_topology_answer_in_run_and_batch_outputs(tmp_path: Path) -> None:
    question_id = "semantic-pi-line-11-e2e"
    runs_path = ROOT / "runs" / question_id
    shutil.rmtree(runs_path, ignore_errors=True)

    pi = tmp_path / "scripted-pi"
    pi.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, os, subprocess, sys, time\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "prompt=json.loads(input())\n"
        "prompt_text=prompt.get('message', prompt) if isinstance(prompt,dict) else prompt\n"
        "runtime=json.load(open(os.environ['CAPABILITY_AGENT_RUNTIME_DESCRIPTOR'],encoding='utf-8'))\n"
        "if runtime.get('schema') == 'capability-agent-runtime/1.0':\n"
        " application=runtime['application']; core=runtime['core']; domain=runtime['domains'][0]\n"
        " if any(name in core for name in ('trajectoryRequestsPath','trajectoryCaptureStatePath','trajectoryAllowedRefsPath','trajectoryAcksPath')): raise RuntimeError('generic single-run descriptor unexpectedly publishes capture channels')\n"
        " capture_enabled=False\n"
        "elif 'schema' not in runtime and runtime['protocol'] == 'grid-capability':\n"
        " application={'workspacePath':runtime['workspace_path'],'piRuntime':runtime['pi_runtime']}\n"
        " core={'activeTurnPath':runtime['active_turn_path'],'trajectoryRequestsPath':runtime['trajectory_requests_path'],'trajectoryCaptureStatePath':runtime['trajectory_capture_state_path'],'trajectoryAllowedRefsPath':runtime['trajectory_allowed_refs_path'],'trajectoryAcksPath':runtime['trajectory_acks_path']}\n"
        " domain={'toolCatalogPath':runtime['tool_catalog_path'],'guideIndexPath':runtime['guide_index_path'],'workspacePath':runtime['workspace_path']}\n"
        " capture_enabled=True\n"
        "else: raise RuntimeError('unknown runtime descriptor contract')\n"
        "def sort_json(value):\n"
        " if isinstance(value,list): return [sort_json(item) for item in value]\n"
        " if isinstance(value,dict): return {key:sort_json(value[key]) for key in sorted(value)}\n"
        " return value\n"
        "def digest(value):\n"
        " return hashlib.sha256(json.dumps(sort_json(value),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()\n"
        "def write_json_atomic(path, value):\n"
        " encoded=json.dumps(sort_json(value),ensure_ascii=False,separators=(',',':'))+'\\n'\n"
        " tmp=path.with_name(f'.{path.name}.{os.getpid()}.tmp')\n"
        " tmp.write_text(encoded,encoding='utf-8')\n"
        " tmp.replace(path)\n"
        "def system_prompt():\n"
        " if '--system-prompt' in sys.argv:\n"
        "  path=sys.argv[sys.argv.index('--system-prompt')+1]\n"
        "  return Path(path).read_text(encoding='utf-8')\n"
        " return None\n"
        "def argv_value(name, fallback):\n"
        " if name in sys.argv:\n"
        "  return sys.argv[sys.argv.index(name)+1]\n"
        " return fallback\n"
        "def semantic_tools(catalog):\n"
        " tools=[{'name':tool['name'],'description':tool['description'],'parameters':tool['input_schema']} for tool in catalog['tools']]\n"
        " tools.append({'name':'grid_guide_open','description':'Open a packaged grid analysis guide.','parameters':{'type':'object','additionalProperties':False,'properties':{'resource_id':{'type':'string','minLength':1}},'required':['resource_id']}})\n"
        " return tools\n"
        "def runtime_identity():\n"
        " return application['piRuntime']\n"
        "def wait_for_ack(request_id, expected_digest):\n"
        " ack_dir=core['trajectoryAcksPath']\n"
        " path=Path(ack_dir)/f'{request_id}.committed.json'\n"
        " deadline=time.monotonic()+10\n"
        " while time.monotonic()<deadline:\n"
        "  if path.exists():\n"
        "   ack=json.loads(path.read_text(encoding='utf-8'))\n"
        "   if ack.get('semantic_request_sha256')!=expected_digest or ack.get('status')!='committed': raise RuntimeError('invalid trajectory request ack')\n"
        "   mark('model_request_committed')\n"
        "   return\n"
        "  time.sleep(0.025)\n"
        " raise RuntimeError('timed out waiting for trajectory request ack')\n"
        "def mark(name):\n"
        " order_path=Path(application['workspacePath'])/'scripted-canonical-order.jsonl'\n"
        " with order_path.open('a',encoding='utf-8') as f: f.write(json.dumps({'marker':name})+'\\n')\n"
        "catalog=json.load(open(domain['toolCatalogPath'],encoding='utf-8'))\n"
        "if capture_enabled:\n"
        " turn=json.load(open(core['activeTurnPath'],encoding='utf-8'))\n"
        " state=json.load(open(core['trajectoryCaptureStatePath'],encoding='utf-8'))\n"
        " request_id=turn['turn_id']+'-r001'\n"
        " request_path=Path(core['trajectoryRequestsPath'])/request_id/'input.json'\n"
        " request_path.parent.mkdir(parents=True,exist_ok=True)\n"
        " semantic={'model':{'provider':argv_value('--provider','scripted'),'api':'openai-responses','id':argv_value('--model','scripted-model')},'context':{'system_prompt':system_prompt(),'messages':[{'role':'user','content':[{'type':'text','text':str(prompt_text)}]}],'tools':semantic_tools(catalog)},'options':{'transport':'sse','temperature':0}}\n"
        " semantic_digest=digest(semantic)\n"
        " request={'schema_version':'grid-model-request-input/2.0','request_id':request_id,'request_index':1,'turn_id':turn['turn_id'],'captured_at':datetime.now(timezone.utc).isoformat(),'source_event_sequences':state['source_event_sequences'],'context_revision':state['context_revision'],'context_state_hash':state['context_state_hash'],'runtime':runtime_identity(),'semantic_request':semantic,'semantic_request_sha256':semantic_digest}\n"
        " write_json_atomic(request_path, request)\n"
        " mark('before_model_request')\n"
        " wait_for_ack(request_id, semantic_digest)\n"
        "else:\n"
        " mark('before_model_request')\n"
        "by_cap={tool['capability']:tool for tool in catalog['tools']}\n"
        "mark('provider_enter')\n"
        "def emit(payload): print(json.dumps(payload), flush=True)\n"
        "def grid(capability,args):\n"
        " tool=by_cap[capability]; name=tool['name']; key={'binding_id':'grid','capability_id':capability}\n"
        " emit({'type':'tool_execution_start','toolCallId':capability,'toolName':name,'capability_key':key,'args':args})\n"
        " req={'protocol':'grid-capability','protocol_version':'1.0','request_id':capability,'capability':capability,'arguments':args}\n"
        " r=subprocess.run(['gridctl','request','--workspace',domain['workspacePath']],input=json.dumps(req)+'\\n',text=True,capture_output=True,check=True)\n"
        " response=json.loads(r.stdout)\n"
        " result=response.get('result') or {}\n"
        " refs=[]\n"
        " if isinstance(result.get('evidence_ref'),str): refs.append(result['evidence_ref'])\n"
        " refs.extend(result.get('evidence_refs') or [])\n"
        " emit({'type':'tool_result','toolCallId':capability,'toolName':name,'capability_key':key,'capability':capability,'projector_id':tool.get('projector_id'),'ok':response.get('ok') is True,'result':result,'evidence_refs':refs})\n"
        " return result\n"
        "def guide(resource_id):\n"
        " index=json.load(open(domain['guideIndexPath'],encoding='utf-8'))\n"
        " emit({'type':'tool_execution_start','toolCallId':'guide-1','toolName':'grid_guide_open','args':{'resource_id':resource_id}})\n"
        " text=open(index['resources'][resource_id],encoding='utf-8').read()\n"
        " emit({'type':'tool_execution_end','toolCallId':'guide-1','toolName':'grid_guide_open','isError':False,'result':{'resource_id':resource_id}})\n"
        " return text\n"
        "emit({'type':'response','command':'prompt','success':True})\n"
        "guide('topology-analysis')\n"
        "opened=grid('context.open',{'model_id':'ieee39'})\n"
        "result=grid('topology.branch.endpoints.get',{'context_ref':opened['context_ref'],'kind':'line','namespace':'pandapower_index','identifier':'11'})\n"
        "ref=result['evidence_ref']\n"
        "emit({'type':'text_delta','text':'线路11连接母线6与11。'})\n"
        "emit({'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'线路11连接母线6与11。'}],'usage':{'input':1,'output':1},'stopReason':'stop'}})\n"
        "emit({'type':'agent_end'})\n",
        encoding="utf-8",
    )
    pi.chmod(0o755)
    managed_cli = ROOT / ".grid-agent/runtime/pi/source" / PiRuntimeLock.load(ROOT / "configs/runtime/pi-runtime.lock.json").executable
    original_cli = managed_cli.read_bytes()
    managed_script = managed_cli.with_name("grid-agent-scripted-pi.py")

    try:
        completed = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                "packages/grid-agent",
                "grid-agent",
                "run",
                "--question-id",
                question_id,
                "IEEE-39节点系统中线路11连接哪两个母线?",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "GRID_AGENT_PI_COMMAND": str(pi),
                "GRID_AGENT_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-only-secret",
            },
            text=True,
            capture_output=True,
            timeout=90,
        )

        assert completed.returncode == 0, completed.stderr
        envelope = AnswerEnvelope.model_validate_json(completed.stdout)
        assert envelope.answer_output == "线路11连接母线6与11。"
        assert not (runs_path / "answer-audit.json").exists()
        assert not (runs_path / "answer-draft.json").exists()
        events = [
            json.loads(line)["payload"]
            for line in (runs_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        legacy_query = "grid" + "_query"
        assert not any(event.get("toolName") in {"read", "bash", "shell", legacy_query} for event in events)
        assert not any(event.get("toolName") == "grid_submit_answer" for event in events)
        assert not any(event.get("capability") == "analysis.powerflow.ac.run" for event in events)
        topology_results = [
            event
            for event in events
            if event.get("type") == "tool_result" and event.get("capability") == "topology.branch.endpoints.get"
        ]
        assert len(topology_results) == 1
        topology = topology_results[0]
        assert topology["result"]["branch"]["name"] == "11"
        assert topology["result"]["from_bus"]["name"] == "6"
        assert topology["result"]["to_bus"]["name"] == "11"
        assert topology["evidence_refs"]
        evidence_ref = topology["evidence_refs"][0]
        digest = evidence_ref.removeprefix("evidence:sha256:")
        assert (runs_path / "evidence/network-facts" / f"network-fact-{digest}.json").is_file()
        order_path = runs_path / "scripted-canonical-order.jsonl"
        order = [json.loads(line)["marker"] for line in order_path.read_text(encoding="utf-8").splitlines()]
        request_paths = tuple((runs_path / "core/requests").glob("*/input.json"))
        assert request_paths == ()
        assert order[:2] == ["before_model_request", "provider_enter"]

        questions = tmp_path / "questions.txt"
        questions.write_text("IEEE-39节点系统中线路11连接哪两个母线?\n", encoding="utf-8")
        managed_script.write_bytes(pi.read_bytes())
        managed_cli.write_text(
            'import { spawnSync } from "node:child_process";\n'
            'const result = spawnSync(process.env.PYTHON ?? "python3", [new URL("./grid-agent-scripted-pi.py", import.meta.url).pathname, ...process.argv.slice(2)], { stdio: "inherit" });\n'
            'process.exit(result.status ?? 1);\n',
            encoding="utf-8",
        )
        report = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                "packages/grid-agent",
                "grid-agent",
                "report",
                "--questions",
                str(questions),
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "GRID_AGENT_PI_COMMAND": str(pi),
                "GRID_AGENT_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-only-secret",
            },
            text=True,
            capture_output=True,
            timeout=90,
        )

        assert report.returncode == 0, report.stderr
        report_envelope = AnswerEnvelope.model_validate_json(report.stdout)
        report_root = ROOT / "runs" / report_envelope.question_id
        report_path = ROOT / report_envelope.answer_output
        report_text = report_path.read_text(encoding="utf-8")
        assert "线路11连接母线6与11。" in report_text
        jsonl_records = [json.loads(line) for line in (report_root / "output/answers.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(jsonl_records) == 1
        assert jsonl_records[0]["answer_output"] == "线路11连接母线6与11。"
        report_request_paths = tuple((report_root / "requests").glob("*/input.json"))
        assert len(report_request_paths) == 1
        report_order = [
            json.loads(line)["marker"]
            for line in (report_root / "scripted-canonical-order.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert report_order[:3] == ["before_model_request", "model_request_committed", "provider_enter"]
        report_request = json.loads(report_request_paths[0].read_text(encoding="utf-8"))
        assert report_request["schema_version"] == "grid-model-request-input/2.0"
        assert report_request["semantic_request"]["model"] == {
            "provider": "openai",
            "api": "openai-responses",
            "id": "gpt-5.5",
        }
        report_messages = report_request["semantic_request"]["context"]["messages"]
        assert len(report_messages) == 1
        assert report_messages[0]["role"] == "user"
        assert report_messages[0]["content"][0]["type"] == "text"
        assert "<instruction>\nIEEE-39节点系统中线路11连接哪两个母线?\n</instruction>" in report_messages[0]["content"][0]["text"]
        assert report_request["semantic_request"]["context"]["tools"]
        assert not any(
            tool["name"] == "grid_submit_answer"
            for tool in report_request["semantic_request"]["context"]["tools"]
        )
        assert report_request["semantic_request"]["options"]["transport"] == "sse"
        assert set(report_request["runtime"]) == {
            "pi_coding_agent_version",
            "pi_ai_version",
            "pi_source_commit",
            "pi_patch_set_sha256",
        }
        assert "provider_payload" not in report_request
        assert "test-only-secret" not in json.dumps(report_request, ensure_ascii=False)
        report_ack = json.loads(
            next((ROOT / ".grid-agent/trajectory-acks" / report_envelope.question_id).glob("*.committed.json")).read_text(
                encoding="utf-8"
            )
        )
        assert report_ack["semantic_request_sha256"] == report_request["semantic_request_sha256"]
        assert report_ack["status"] == "committed"
        shutil.rmtree(report_root, ignore_errors=True)
    finally:
        managed_cli.write_bytes(original_cli)
        managed_script.unlink(missing_ok=True)
        shutil.rmtree(runs_path, ignore_errors=True)
