"""Describe only the base environment that passed the image build checks."""
import json
import re
from pathlib import Path

ENVIRONMENT_RECEIPT = Path(__file__).parent.parent / 'runtime-environment.json'


def environment_context(path: Path = ENVIRONMENT_RECEIPT) -> str | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    fields = {'schema', 'python', 'packages', 'commands', 'smoke_capabilities',
              'manifest_sha256', 'lock_sha256'}
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != 'capstone-native-environment/1':
        raise ValueError('Native environment receipt schema is invalid')
    python = value['python']
    if not isinstance(python, dict) or set(python) != {'version', 'implementation'}:
        raise ValueError('Native environment Python receipt is invalid')
    token = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+\-]*\Z')
    for mapping in (python, value['packages'], value['commands']):
        if not isinstance(mapping, dict) or not mapping or any(
            not isinstance(key, str) or not token.fullmatch(key)
            or not isinstance(item, str) or not token.fullmatch(item)
            for key, item in mapping.items()
        ):
            raise ValueError('Native environment version receipt is invalid')
    checks = value['smoke_capabilities']
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, str) or not token.fullmatch(item) for item in checks
    ):
        raise ValueError('Native environment smoke receipt is invalid')
    if any(not isinstance(value[key], str) or not re.fullmatch(r'[a-f0-9]{64}', value[key])
           for key in ('manifest_sha256', 'lock_sha256')):
        raise ValueError('Native environment source identity is invalid')
    plot_context = ''
    if 'matplotlib' in value['packages'] and 'chinese_plots' in checks:
        plot_context = (
            '\nChinese plotting was checked with the preinstalled Noto Sans CJK SC font. '
            'Use matplotlib with the Agg backend and that font for static Chinese charts. '
            'Do not download fonts or enumerate installed fonts unless a specific rendering failure requires it. '
        )
    report_context = ''
    if 'capstone-report' in value['commands'] and 'standalone_reports' in checks:
        report_context = (
            '\nFor a standalone HTML report, use capstone-report --spec report.json --output report.html. '
            'Paths are relative to the task working directory. Minimal spec: '
            '{"schema":"capstone-report/1","title":"Report","sections":'
            '[{"id":"results","title":"Results","blocks":'
            '[{"type":"paragraph","text":"Supported findings"},'
            '{"type":"table","csv":"metrics.csv"},'
            '{"type":"figure","path":"chart.png","caption":"Describe the actual chart"}]}]}. '
            'CSV values are displayed unchanged; prepare display units and percentages in the source CSV. '
            'The renderer embeds figures and creates section anchors and figure numbers. '
            'Its receipt and source hashes do not prove factual accuracy: inspect the final report, '
            'check captions against actual charts and claims against verified results. '
            'Native scripts remain available when this block format does not fit the requested output. '
        )
    presentation_context = ''
    if ('capstone-report' in value['commands'] and 'python-pptx' in value['packages']
            and 'Pillow' in value['packages'] and 'standalone_presentations' in checks):
        presentation_context = (
            '\nFor an ordinary PPTX deck, prefer the verified reusable renderer instead of generating layout or assembly Python: '
            'capstone-report --spec slides.json --output slides.pptx. '
            'Write only supported content, captions and source notes. Reuse saved figures instead of regenerating them for assembly. '
            'Minimal spec: {"schema":"capstone-presentation/1","title":"Report","slides":'
            '[{"title":"Findings","source_notes":["Saved source revision"],"blocks":'
            '[{"type":"paragraph","text":"Actual supported findings"},'
            '{"type":"table","csv":"display.csv","columns":["label","value"],"max_rows":100},'
            '{"type":"figure","path":"chart.png","caption":"Caption matched to the saved chart"}]}]}. '
            'Bullets use {"type":"bullets","items":["Supported point"]}. '
            'The helper adds a title cover, wraps text and paginates, repeating table headers; inspect receipt.slides for the actual slide count. '
            'It never recalculates CSV strings or infers conclusions. '
            'Use 1..8 selected CSV columns and an explicit max_rows of 1..1000; excess rows fail rather than silently truncate. '
            'Prepare a compact display CSV from actual computations if the source is too large or wide. '
            'Only saved PNG/JPEG figures are supported for PPTX; no raw HTML, scripts, external image URLs or arbitrary layouts. '
            'Source notes must be brief. Processing budgets: JSON 1 MiB, CSV 16 MiB, each image 8 MiB/20 million pixels, '
            'all images 32 MiB, at most 40 content records and 120 rendered slides. '
            'Check the resulting deck and source hashes; rendering does not verify claims. '
            'Use native Python only if the verified capability is absent or the requested layout is unsupported. '
        )
    if presentation_context and 'template_presentations' in checks:
        presentation_context += (
            ' To generate with the State Grid template, add "template":{"id":"state-grid"} to the presentation spec. '
            'For an admitted uploaded PPTX template, use "template":{"path":"<staged relative path>"}. '
            'Omit template to retain the original untemplated layout. Template rendering requires 16:9; '
            'the renderer preserves template masters and cover pictures and removes sample slides. '
            'Save the content spec and referenced files for later rendering with another template. '
            'Check all generated pages visually before calling the layout accepted; template loading alone does not prove design quality. '
            ' Template output is a briefing: plan one core message per content record with concise, connected reasoning alongside its evidence. '
            'First save the report argument: audience and purpose, chapter questions, page claims, evidence and implications. '
            'A complete report has cover, agenda, connected chapters, synthesized conclusions and closing; do not force the source page count. '
            'Derive themes from the admitted findings with an opening overview, themed analysis and closing synthesis. '
            'The agenda lists only main chapter titles; every opinion page responds to one agenda theme. '
            'Each opinion page must explain how its evidence supports the title and what follows; avoid disconnected numbers or slogan fragments. '
            'Use role:"agenda" for the agenda, section:"<chapter title>" on content slides, and role:"closing" on the final record. '
            'The chapter label uses the same bold title typeface at 22pt on the right; the separate 27pt claim stays on the left. '
            'The State Grid agenda reuses its dedicated artwork and numbered bars, with up to six chapter titles; do not substitute a data table. '
            'Uploaded templates may select their numbered-row agenda with template.agenda_slide. '
            'When an agenda is present, each content section must exactly match its titles and follow their order; chapter_order errors require fixing the spec before publishing. '
            'Closing reuses cover branding and accepts zero blocks or one short paragraph. Omit role for ordinary content. '
            'Each content record stays on one slide; a figure/table and its points share a composition. '
            'Keep the evidence-to-claim explanation and any limit that changes the claim in visible paragraph or bullet blocks. '
            'Use speaker_notes for detailed derivations and supplementary context, not the missing argument. '
            'Do not copy report-length narration into slides; use short source_notes for citations. '
            'A slide_overflow diagnostic requires editing the page plan or summarizing its visible content; do not shrink fonts, '
            'silently split the page, delete support, or assert that unreadable output is accepted. '
            '\nVISIBLE ARGUMENT REVIEW: Before delivery, review the saved spec and read back actual PPTX text frames and table cells, excluding notes. '
            'Assess each opinion page as a reader who has only that visible page and its figure, not the argument plan or speaker notes. '
            'For each page, identify its title claim, decisive evidence/comparison, the inference connecting them, '
            'and a supported implication or material boundary. The visible explanation must answer why these findings support this title '
            'and how this page advances its chapter. Speaker notes do not count as visible support. '
            'Repeating plotted numbers, paraphrasing the title, listing labels or adding a generic recommendation does not supply an inference. '
            'For example, "A +12%; B +3%" is a reading; "A rises faster than B, so the increase is uneven rather than uniform" explains the comparison. '
            'Use only inferences justified by the saved results; do not invent causal mechanisms or turn historical observations into future operating instructions. '
            'Act as a skeptical reader: try to disprove each inference against the admitted evidence before accepting it. '
            'Identify the strongest contrary reading or missing comparison; if the same evidence allows it, qualify or narrow the claim. '
            'Check that the inference preserves the evidence\'s population, time window, measurement, aggregation and comparison basis. '
            'Distinguish an observed pattern, a change in that pattern, a causal explanation, a forecast and a recommendation; '
            'support for one does not automatically establish the others. Check the entire visible page for contradictions, '
            'including between title, prose, table, caption and limits, and check whether its chapter is a coherent question rather than a catch-all. '
            'A review passes only when the evidence supports the actual inference, not because four argument fields are present. '
            'When agent_llm_submit is granted, use an independent text-only reader for an evidence briefing after the draft exists. '
            'Supply a bounded packet of actual visible page text, chapter bindings and relevant admitted facts with units, windows and limits; '
            'exclude speaker notes, the author\'s argument plan and prior self-review verdicts so the reader tests the page itself. '
            'Ask for concrete unsupported inferences, contradictions and missing explanatory links, with page/quote/evidence locations, '
            'not a passing score or confirmation of the author\'s conclusions. Split by coherent chapter groups only if the granted input budget requires it. '
            'Collect actual replies, verify each concern against saved sources, and revise the claim or explanation when warranted. '
            'Save the returned critique and its issue dispositions, tied to the reviewed and final spec digests. '
            'A critic is another model observation, not Authority evidence or a factual certificate. '
            'Do not keep repeating unchanged reviews; use the bounded repair rounds below. If no isolated reader is granted, state that review was self-review only. '
            'Do not enforce a fixed bullet count, sentence pattern or minimum word count. A compact paragraph may be stronger than three fragments. '
            'A boundary page can explain what a missing comparison prevents; it need not invent an operational recommendation. '
            'If support exists only in notes, bring its essential explanation into visible blocks and remove redundant readings; '
            'if the evidence cannot support the claim, narrow the claim instead. Preserve readable template composition. '
            'Review the actual final spec again after any overflow-driven shortening so layout repair cannot silently remove reasoning. '
            'Save a per-page review product with the final spec SHA-256, page/section/title, quoted visible support, '
            'identified inference, contrary evidence or missing comparisons considered, actual defects, revisions and unresolved checks. '
            'Distinguish content review, source checks and visual checks. '
            'Use at most two targeted repair rounds for observed defects. Do not claim semantic or visual acceptance solely from renderer success '
            'or a self-assigned score; disclose unresolved issues and unavailable checks. '
        )
    if presentation_context and {'template_presentations','argument_presentations'} <= set(checks):
        presentation_context += (
            '\nFor new evidence briefings with a template, use schema:"capstone-presentation/2". '
            'Each ordinary content record requires argument:{"explanation":"The evidence-to-claim explanation for this page"}. '
            'Derive explanation from the saved page argument; write concise supported reasoning, not a label or another reading. '
            'Keep the saved figure/table and any selected facts in blocks. The renderer adds argument.explanation as a visible paragraph, '
            'includes it in the real layout budget and binds its SHA-256/page in receipt.visible_arguments. '
            'Do not duplicate the explanation in blocks. Agenda/closing records omit argument. '
            'An omitted explanation is a contract error; an overlong one is slide_overflow. Revise the composition while keeping '
            'its inference visible. Do not downgrade to schema1 to bypass this new-briefing contract. '
            'Schema1 remains for original untemplated output and unchanged historical rerenders. '
            'The contract guarantees visible authored explanation, not semantic accuracy or adequate reasoning; perform the skeptical review above. '
        )
    return (
        'Verified base programming environment (default Python, not a separately selected MCP interpreter). '
        'Use these preinstalled libraries for authorized tasks; do not reinstall them or run a package '
        'inventory unless an observed incompatibility requires it. Skills and MCP permissions are listed '
        'separately. Installed HTTP clients do not grant external network access. '
        + json.dumps(value, ensure_ascii=False, sort_keys=True)
        + plot_context
        + report_context
        + presentation_context
    )
