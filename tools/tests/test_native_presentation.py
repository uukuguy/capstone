"""Real PPTX bytes, layout bounds, exact source strings and confined paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from PIL import Image

def test_preflight_checks_without_replacing_existing_output(tmp_path):
    spec={'schema':'capstone-presentation/1','title':'Check','slides':[{'title':'One','blocks':[{'type':'paragraph','text':'Text'}]}]}
    (tmp_path/'spec.json').write_text(json.dumps(spec))
    output=tmp_path/'existing.pptx';output.write_bytes(b'previous')
    result=subprocess.run([sys.executable,str(SCRIPT),'--spec','spec.json','--output','existing.pptx','--check-only'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert output.read_bytes()==b'previous'
    assert json.loads(result.stdout)['output_written'] is False

def test_reports_all_independent_block_errors_before_writing(tmp_path):
    (tmp_path/'data.csv').write_text('name,value\na,1\n')
    spec={'schema':'capstone-presentation/1','title':'Check','slides':[{'title':'One','blocks':[
        {'type':'table','csv':'data.csv','columns':['missing'],'max_rows':5},
        {'type':'figure','path':'missing.png','caption':'Missing'}]}]}
    (tmp_path/'spec.json').write_text(json.dumps(spec))
    result=subprocess.run([sys.executable,str(SCRIPT),'--spec','spec.json','--output','result.pptx'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==2
    detail=json.loads(result.stderr.splitlines()[-1])
    assert len(detail['errors'])==2
    assert detail['errors'][0]['location']=='slides[0].blocks[0]'
    assert detail['errors'][1]['location']=='slides[0].blocks[1]'
    assert not (tmp_path/'result.pptx').exists()
from pptx import Presentation
import pytest

SCRIPT = Path(__file__).parents[2] / 'tools/native_report.py'


def test_briefing_preserves_unicode_numeric_ranges_at_line_boundaries():
    import importlib.util
    loaded=importlib.util.spec_from_file_location('briefing_layout',SCRIPT.with_name('native_presentation_layout.py'))
    module=importlib.util.module_from_spec(loaded);loaded.loader.exec_module(module)
    for expression in ['18—22 时','18–22 时']:
        lines=module.wrap_briefing('覆盖'+expression,12)
        assert any(expression in line for line in lines),lines


def test_template_report_roles_preserve_chapter_context_and_branded_closing(tmp_path):
    value = spec([], template={'id':'state-grid'})
    value['slides'] = [
        {'role':'agenda','title':'汇报目录','blocks':[{'type':'paragraph','text':'一、总体态势：变化是什么？'}]},
        {'section':'一、总体态势','title':'峰值增长集中于晚间',
         'blocks':[{'type':'paragraph','text':'晚间增幅高于午间，支持关注晚峰的判断。'}]},
        {'role':'closing','title':'汇报完毕','blocks':[{'type':'paragraph','text':'请批评指正'}]},
    ]
    result = run(tmp_path,value)
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    assert len(deck.slides) == 4
    assert '一、总体态势' in deck_text(deck)
    chapter = next(s for s in deck.slides[2].shapes if s.has_text_frame and s.text == '一、总体态势')
    assert chapter.text_frame.paragraphs[0].font.size.pt == 14
    from pptx.enum.text import PP_ALIGN
    assert chapter.text_frame.paragraphs[0].alignment == PP_ALIGN.RIGHT
    assert chapter.top < 914400
    opinion = next(s for s in deck.slides[2].shapes if s.has_text_frame and s.text == '峰值增长集中于晚间')
    assert opinion.left + opinion.width < chapter.left
    closing = deck.slides[-1]
    assert closing.slide_layout.part.partname == deck.slides[0].slide_layout.part.partname
    assert any(s.shape_type == 13 for s in closing.shapes)
    title = next(s for s in closing.shapes if s.has_text_frame and s.text == '汇报完毕')
    assert title.top > 914400
    assert str(title.text_frame.paragraphs[0].font.color.rgb) == 'FFFFFF'
    assert '请批评指正' in deck_text(deck)


@pytest.mark.parametrize('slides', [
    [{'role':'unknown','title':'Bad','blocks':[]}],
    [{'role':'closing','title':'End','blocks':[]},{'title':'Later','blocks':[]}],
    [{'role':'closing','title':'End','blocks':[{'type':'figure','path':'x.png','caption':'Bad'}]}],
])
def test_template_rejects_invalid_report_roles_without_replacing_output(tmp_path,slides):
    value=spec([],template={'id':'state-grid'});value['slides']=slides
    (tmp_path/'report.pptx').write_bytes(b'prior product')
    result=run(tmp_path,value)
    assert result.returncode == 2
    assert (tmp_path/'report.pptx').read_bytes() == b'prior product'


def test_chapter_navigation_reserves_title_space_instead_of_overlapping(tmp_path):
    value=spec([],template={'id':'state-grid'})
    value['slides']=[{'section':'一、总体态势','title':'数据支持这一判断但这个观点标题过长需要重新提炼而不能遮住章节名称','blocks':[]}]
    (tmp_path/'report.pptx').write_bytes(b'prior product')
    result=run(tmp_path,value)
    assert result.returncode == 2 and 'slide_overflow' in result.stderr
    assert (tmp_path/'report.pptx').read_bytes() == b'prior product'


def test_template_preserves_master_size_and_removes_sample_content(tmp_path):
    template = Presentation()
    template.slide_width = 12192000
    template.slide_height = 6858000
    sample = template.slides.add_slide(template.slide_layouts[0])
    sample.shapes.title.text = 'SAMPLE MUST NOT SHIP'
    template.save(tmp_path/'brand.pptx')
    result = run(tmp_path, spec([{'type':'paragraph','text':'Verified content'}],
        template={'path':'brand.pptx'}))
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    assert deck.slide_width == template.slide_width
    assert deck.slide_height == template.slide_height
    assert 'SAMPLE MUST NOT SHIP' not in deck_text(deck)
    assert 'Verified content' in deck_text(deck)
    receipt = json.loads(result.stdout)
    assert receipt['template']['sha256'] == hashlib.sha256((tmp_path/'brand.pptx').read_bytes()).hexdigest()
    with ZipFile(tmp_path/'brand.pptx') as source, ZipFile(tmp_path/'report.pptx') as output:
        assert source.read('ppt/theme/theme1.xml') == output.read('ppt/theme/theme1.xml')


def test_builtin_state_grid_template_is_available_without_host_files(tmp_path):
    result = run(tmp_path, spec([{'type':'paragraph','text':'Internal evaluation'}],
        template={'id':'state-grid'}))
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['template']['id'] == 'state-grid'
    deck = Presentation(tmp_path/'report.pptx')
    assert len(deck.slides) == 2
    assert any(shape.shape_type == 13 for shape in deck.slides[0].shapes)
    assert not any(text in deck_text(deck) for text in ['演示功能清单','核心观点的提炼与总结'])


def test_builtin_cover_resolves_inherited_light_text_color(tmp_path):
    result = run(tmp_path, spec([{'type':'paragraph','text':'Content'}], template={'id':'state-grid'}))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['template']['cover_text_rgb'] == 'FFFFFF'


def test_builtin_content_uses_the_templates_actual_body_layout(tmp_path):
    result = run(tmp_path, spec([{'type':'paragraph','text':'Content'}], template={'id':'state-grid'}))
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    original = Presentation(SCRIPT.parent/'presentation-templates/state-grid.pptx')
    assert str(deck.slides[1].slide_layout.part.partname) == str(original.slides[2].slide_layout.part.partname)


def test_template_combines_figure_and_key_points_without_fragmenting(tmp_path):
    Image.new('RGB',(640,360),'teal').save(tmp_path/'figure.png')
    result = run(tmp_path, spec([
        {'type':'bullets','items':['第一项观察','第二项观察','第三项观察']},
        {'type':'figure','path':'figure.png','caption':'保存的图表'}], template={'id':'state-grid'}))
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    assert len(deck.slides) == 2
    assert any(s.shape_type == 13 for s in deck.slides[1].shapes)
    assert '第三项观察' in deck_text(deck)


def test_template_combines_table_and_key_points_on_one_page(tmp_path):
    (tmp_path/'data.csv').write_text('对象,数值\n甲,001.2300\n乙,12.50%\n')
    result = run(tmp_path, spec([
        {'type':'table','csv':'data.csv','max_rows':10},
        {'type':'bullets','items':['保留原始字符串','不重新解释业务事实']}],template={'id':'state-grid'}))
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    assert len(deck.slides) == 2
    assert '001.2300' in deck_text(deck) and '12.50%' in deck_text(deck)


def test_template_overflow_is_explicit_and_preserves_old_product(tmp_path):
    (tmp_path/'report.pptx').write_bytes(b'previous product')
    result = run(tmp_path, spec([{'type':'bullets','items':['过长的说明'*60]*20}], template={'id':'state-grid'}))
    assert result.returncode == 2
    assert 'slide_overflow' in result.stderr
    assert (tmp_path/'report.pptx').read_bytes() == b'previous product'


def test_template_preserves_detail_in_speaker_notes_without_filling_the_slide(tmp_path):
    value = spec([{'type':'bullets','items':['核心要点']}],template={'id':'state-grid'})
    detail = '完整口径与推导保留在备注。'*50
    value['slides'][0]['speaker_notes'] = detail
    result = run(tmp_path,value)
    assert result.returncode == 0, result.stderr
    deck = Presentation(tmp_path/'report.pptx')
    assert len(deck.slides) == 2
    assert detail not in deck_text(deck)
    assert detail in deck.slides[1].notes_slide.notes_text_frame.text


def test_briefing_wrap_keeps_numbers_and_dates_intact():
    import runpy
    wrap = runpy.run_path(str(SCRIPT.parent/'native_presentation_layout.py'))['wrap_briefing']
    lines = wrap('最高负荷1,082.8 GW，窗口2025-06-15结束，同比+13.5%',16)
    for token in ['1,082.8','2025-06-15','+13.5%']:
        assert any(token in line for line in lines), (token,lines)
    with pytest.raises(ValueError):
        wrap('2025-06-15',5)


def test_template_rejects_external_relationships_without_replacing_output(tmp_path):
    template = Presentation()
    page = template.slides.add_slide(template.slide_layouts[0])
    page.shapes.title.text = 'Example'
    page.shapes.title.text_frame.paragraphs[0].runs[0].hyperlink.address = 'https://example.com'
    template.save(tmp_path/'external.pptx')
    (tmp_path/'report.pptx').write_bytes(b'old product')
    result = run(tmp_path, spec([{'type':'paragraph','text':'Content'}], template={'path':'external.pptx'}))
    assert result.returncode == 2
    assert 'external' in result.stderr.lower()
    assert (tmp_path/'report.pptx').read_bytes() == b'old product'


def spec(blocks, **extra):
    return {'schema':'capstone-presentation/1','title':'通用研究汇报',
        'slides':[{'title':'已保存的观察','blocks':blocks,'source_notes':['Source dataset revision r1']}],**extra}


def run(directory, value, output='report.pptx'):
    (directory/'slides.json').write_text(json.dumps(value,ensure_ascii=False))
    return subprocess.run([sys.executable,str(SCRIPT),'--spec','slides.json','--output',output],
        cwd=directory,capture_output=True,text=True)


def deck_text(deck):
    return '\n'.join(shape.text if shape.has_text_frame else '\n'.join(cell.text for row in shape.table.rows for cell in row.cells)
        if shape.has_table else '' for slide in deck.slides for shape in slide.shapes)


def test_real_pptx_has_exact_csv_strings_image_notes_and_source_hashes(tmp_path):
    (tmp_path/'data.csv').write_text('label,value,ratio\n甲省,001.2300,12.50%\n乙省,未记录,1.00%\n')
    Image.new('RGB',(320,180),'teal').save(tmp_path/'figure.png')
    value=spec([{'type':'paragraph','text':'仅排版已有观察；<script>是普通文字。'},
        {'type':'table','csv':'data.csv','max_rows':20,'caption':'保存的原始字符串'},
        {'type':'figure','path':'figure.png','caption':'已保存图片，不新增结论'}])
    result=run(tmp_path,value)
    assert result.returncode==0,result.stderr
    output=tmp_path/'report.pptx'
    assert output.read_bytes().startswith(b'PK')
    deck=Presentation(output)
    assert len(deck.slides)>=4
    assert str(deck.slides[0].background.fill.fore_color.rgb) == '172B3B'
    assert str(deck.slides[1].background.fill.fore_color.rgb) == 'F3F7F7'
    text=deck_text(deck)
    assert all(item in text for item in ['001.2300','12.50%','未记录','Source dataset revision r1','<script>'])
    assert sum(shape.shape_type==13 for slide in deck.slides for shape in slide.shapes)==1
    assert all('Source dataset revision r1' in slide.notes_slide.notes_text_frame.text for slide in list(deck.slides)[1:])
    receipt=json.loads(result.stdout)
    assert receipt['schema']=='capstone-presentation-receipt/1' and receipt['slides']==len(deck.slides)
    for path,digest in receipt['source_sha256'].items():assert hashlib.sha256((tmp_path/path).read_bytes()).hexdigest()==digest
    with ZipFile(output) as archive:
        assert not any(b'TargetMode="External"' in archive.read(path) for path in archive.namelist() if path.endswith('.rels'))
    for slide in deck.slides:
        for shape in slide.shapes:
            assert 0<=shape.left and 0<=shape.top
            assert shape.left+shape.width<=deck.slide_width+100
            assert shape.top+shape.height<=deck.slide_height+100


def test_long_chinese_text_and_csv_rows_paginate_without_silent_loss(tmp_path):
    paragraphs='。'.join(f'第{i}项保留的说明与限制' for i in range(160))
    (tmp_path/'many.csv').write_text('name,value\n'+''.join(f'row-{i},00{i}.50%\n' for i in range(65)))
    result=run(tmp_path,spec([{'type':'paragraph','text':paragraphs},
        {'type':'table','csv':'many.csv','max_rows':65}]))
    assert result.returncode==0,result.stderr
    deck=Presentation(tmp_path/'report.pptx');text=deck_text(deck)
    assert len(deck.slides)>5 and '第159项' in text.replace('\n','') and 'row-64' in text and '0064.50%' in text
    tables=[shape.table for slide in deck.slides for shape in slide.shapes if shape.has_table]
    assert len(tables)>1 and all(table.cell(0,0).text=='name' for table in tables)
    assert sum(len(table.rows)-1 for table in tables)==65


@pytest.mark.parametrize('block', [
    {'type':'html','text':'<script>x</script>'},
    {'type':'table','csv':'../outside.csv','max_rows':5},
    {'type':'figure','path':'https://example.test/image.png','caption':'remote'},
    {'type':'figure','path':'active.svg','caption':'unsupported SVG'},
    {'type':'paragraph','text':'ok','script':'no'},
])
def test_arbitrary_code_remote_paths_and_unknown_shapes_fail_without_output(tmp_path,block):
    (tmp_path/'active.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>')
    result=run(tmp_path,spec([block]))
    assert result.returncode==2 and not (tmp_path/'report.pptx').exists()


def test_csv_row_budget_is_explicit_and_never_silently_truncates(tmp_path):
    (tmp_path/'data.csv').write_text('name,value\na,1\nb,2\n')
    result=run(tmp_path,spec([{'type':'table','csv':'data.csv','max_rows':1}]))
    assert result.returncode==2 and 'max_rows' in result.stderr
    assert not (tmp_path/'report.pptx').exists()


def test_spec_size_and_source_symlinks_cannot_bypass_workspace_boundary(tmp_path):
    workspace=tmp_path/'workspace';workspace.mkdir()
    Image.new('RGB',(2,2),'red').save(tmp_path/'outside.png')
    (workspace/'link.png').symlink_to(tmp_path/'outside.png')
    assert run(workspace,spec([{'type':'figure','path':'link.png','caption':'symlink'}])).returncode==2
    assert run(workspace,spec([]),output='../outside.pptx').returncode==2
    assert run(workspace,spec([]),output='slides.json').returncode==2
    assert run(workspace,spec([{'type':'paragraph','text':'x'*1100000}])).returncode==2
    assert not (workspace/'report.pptx').exists()


@pytest.mark.parametrize('block', [
    {'type':'table','csv':'data.csv','max_rows':True},
    {'type':'table','csv':'data.csv'},
    {'type':'table','csv':'data.csv','max_rows':1001},
    {'type':'table','csv':'data.csv','max_rows':2,'columns':['unknown']},
    {'type':'table','csv':'data.json','max_rows':2},
])
def test_table_contract_rejects_ambiguous_or_unbounded_requests(tmp_path,block):
    (tmp_path/'data.csv').write_text('name,value\na,1\n')
    (tmp_path/'data.json').write_text('name,value\na,1\n')
    assert run(tmp_path,spec([block])).returncode==2
    assert not (tmp_path/'report.pptx').exists()


def test_source_processing_and_pixel_budgets_fail_before_output(tmp_path):
    with (tmp_path/'huge.csv').open('wb') as output:output.truncate(16*1024*1024+1)
    assert run(tmp_path,spec([{'type':'table','csv':'huge.csv','max_rows':10}])).returncode==2
    Image.new('1',(5000,5000)).save(tmp_path/'too-many-pixels.png')
    assert run(tmp_path,spec([{'type':'figure','path':'too-many-pixels.png','caption':'large'}])).returncode==2
    assert not (tmp_path/'report.pptx').exists()


def test_hardlink_output_cannot_replace_spec_or_saved_source(tmp_path):
    (tmp_path/'source.csv').write_text('name,value\na,1\n')
    (tmp_path/'report.pptx').hardlink_to(tmp_path/'source.csv')
    before=(tmp_path/'source.csv').read_bytes()
    result=run(tmp_path,spec([{'type':'table','csv':'source.csv','max_rows':10}]))
    assert result.returncode==2
    assert (tmp_path/'source.csv').read_bytes()==before


@pytest.mark.parametrize('extension', ['html','pptx'])
@pytest.mark.parametrize('source_kind', ['spec','csv','image'])
def test_input_hardlinks_cannot_import_external_spec_csv_or_image(tmp_path,extension,source_kind):
    workspace=tmp_path/'workspace';workspace.mkdir()
    if source_kind=='csv':
        source=tmp_path/'outside.csv';source.write_text('label,value\nexternal,001.25\n')
        (workspace/'data.csv').hardlink_to(source)
        blocks=[{'type':'table','csv':'data.csv',**({'max_rows':5} if extension=='pptx' else {})}]
    elif source_kind=='image':
        source=tmp_path/'outside.png';Image.new('RGB',(2,2),'red').save(source)
        (workspace/'figure.png').hardlink_to(source)
        blocks=[{'type':'figure','path':'figure.png','caption':'External hardlinked image'}]
    else:
        blocks=[{'type':'paragraph','text':'External hardlinked spec'}]
    value=spec(blocks) if extension=='pptx' else {'title':'Report','sections':[{'id':'results','title':'Results','blocks':blocks}]}
    if source_kind=='spec':
        source=tmp_path/'outside.json';source.write_text(json.dumps(value))
        (workspace/'slides.json').hardlink_to(source)
    else:
        (workspace/'slides.json').write_text(json.dumps(value))
    before=source.read_bytes()
    result=subprocess.run([sys.executable,str(SCRIPT),'--spec','slides.json','--output','report.'+extension],
        cwd=workspace,capture_output=True,text=True)
    assert result.returncode==2 and 'hardlinked' in result.stderr
    assert not (workspace/('report.'+extension)).exists()
    assert source.read_bytes()==before


def test_build_smoke_checks_real_pptx_cli_and_sources(tmp_path):
    import importlib.util
    loaded=importlib.util.spec_from_file_location('native_analysis_smoke',SCRIPT.with_name('native_analysis_smoke.py'))
    module=importlib.util.module_from_spec(loaded);loaded.loader.exec_module(module)
    module.exercise_presentation(tmp_path,renderer=[sys.executable,str(SCRIPT)])
    deck=Presentation(tmp_path/'presentation.pptx')
    assert len(deck.slides)>=4 and '001.2300' in deck_text(deck)
