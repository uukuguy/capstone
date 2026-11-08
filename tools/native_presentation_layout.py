"""Fit one planned briefing page without splitting or shrinking its content."""
import csv
import io
import re
import unicodedata
from pathlib import Path


def wrap_briefing(value, width):
    """Keep numeric expressions, dates and Latin words whole at line breaks."""
    pattern = re.compile(r'[+−-]?(?:\d[\d,]*(?:\.\d+)?|\.\d+)(?:[/:−-]\d+)*'
                         r'(?:[eE][+-]?\d+)?(?:%|\s+[A-Za-z°℃]{1,5}(?![A-Za-z])|\s*[年月日时分秒天])?'
                         r'|[A-Za-z_][A-Za-z0-9_./%-]*|.')
    def units(text):
        return sum(0 if unicodedata.combining(c) else 2 if ord(c)>127 or c.isupper() or c in 'mw@%#&' else 1 for c in text)
    lines=[]
    for source in value.split('\n'):
        tokens=[]
        for match in pattern.finditer(source):
            token=match.group()
            if token in '，。；：！？、）】》”’.,;:!?)' and tokens:
                tokens[-1]+=token
            else:
                tokens.append(token)
        current='';used=0
        for token in tokens:
            size=units(token)
            if size>width:
                raise ValueError('A number, date or word exceeds its briefing text frame; move it to notes or use a wider composition')
            if current and used+size>width:
                lines.append(current.rstrip());current='';used=0
            if not current:
                token=token.lstrip();size=units(token)
            current+=token;used+=size
        lines.append(current.rstrip())
    return lines


def render_briefing_slide(content, *, workspace, page, textbox, wrap, literal, error, title_color, location):
    from PIL import Image
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    def fail(message):
        raise error(message, diagnostic={'code':'slide_overflow', 'location':location,
            'output_written':False, 'recovery':
            'Keep one main point on this planned page. Shorten visible text or the display table; '
            'move detail to speaker_notes or a saved appendix. Do not silently split the page or shrink its fonts.'})

    def fields(value, required, optional=()):
        if not isinstance(value,dict) or not set(required) <= value.keys() or set(value)-set(required)-set(optional):
            raise error('missing or unknown briefing block fields at '+location)

    text, visual = [], None
    stats = {'figures':0, 'tables':0, 'table_rows':0, 'image_bytes':0}
    for index, block in enumerate(content['blocks']):
        if not isinstance(block,dict):
            raise error('briefing blocks must be objects')
        kind = block.get('type')
        if kind == 'paragraph':
            fields(block,('type','text'))
            text.append((False,literal(block['text'],'paragraph',20000)))
        elif kind == 'bullets':
            fields(block,('type','items'))
            if not isinstance(block['items'],list) or not 1 <= len(block['items']) <= 100:
                raise error('bullet items must contain 1..100 strings')
            text.extend((True,literal(item,'bullet',2000)) for item in block['items'])
        elif kind in {'figure','table'}:
            if visual is not None:
                fail('A briefing page supports one visual and its key points; plan separate points explicitly')
            if kind == 'figure':
                fields(block,('type','path','caption'))
                name = block['path']
                if not isinstance(name,str) or Path(name).suffix.lower() not in {'.png','.jpg','.jpeg'}:
                    raise error('PPTX figures must be saved PNG or JPEG files')
                data = workspace.read(name,location=f'{location}.blocks[{index}].path',maximum=16*1024*1024)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format not in {'PNG','JPEG'}:
                        raise error('PPTX figures must contain PNG or JPEG data')
                    width,height = image.size
                    if width*height > 64*1024*1024:
                        raise error('figure exceeds its pixel processing budget')
                    image.verify()
                visual = (kind,data,width,height)
                stats.update(figures=1,image_bytes=len(data))
            else:
                fields(block,('type','csv','max_rows'),('columns','caption'))
                if type(block['max_rows']) is not int or not 1 <= block['max_rows'] <= 1000:
                    raise error('table max_rows must be an integer within 1..1000')
                if not isinstance(block['csv'],str) or Path(block['csv']).suffix.lower() != '.csv':
                    raise error('table sources must be saved CSV files')
                data = workspace.read(block['csv'],location=f'{location}.blocks[{index}].csv',maximum=16*1024*1024)
                csv.field_size_limit(65536)
                reader = csv.reader(io.StringIO(data.decode('utf-8-sig'),newline=''),strict=True)
                header = next(reader,[])
                if not header or any(not h for h in header) or len(set(header)) != len(header):
                    raise error('CSV must have a nonempty unique header')
                columns = block.get('columns',header)
                if (not isinstance(columns,list) or not 1 <= len(columns) <= 8
                        or any(not isinstance(c,str) or c not in header for c in columns)
                        or len(set(columns)) != len(columns)):
                    raise error('select 1..8 unique existing CSV columns for the briefing table')
                indices = [header.index(c) for c in columns]
                rows = []
                for row in reader:
                    if len(rows) >= block['max_rows']:
                        fail('CSV exceeds explicit max_rows; prepare a bounded display table')
                    if len(row) != len(header):
                        raise error('CSV row length does not match its header')
                    selected = [row[i] for i in indices]
                    if any(len(v)>2000 or any(ord(c)<32 and c!='\n' for c in v) for v in selected):
                        raise error('CSV cell exceeds its literal text budget')
                    rows.append(selected)
                visual = (kind,columns,rows)
                stats.update(tables=1,table_rows=len(rows))
            caption = literal(block['caption'],'caption',240) if 'caption' in block else ''
            # A missing table caption is allowed; the figure contract requires one.
            if kind == 'figure' and not caption:
                raise error('figure caption must be nonempty text')
        else:
            raise error('unknown presentation block type')

    def text_lines(width,height):
        units = max(10,int(width*72/11)-2)
        lines = []
        for bullet,value in text:
            if lines:
                lines.append('')
            wrapped = wrap(value,units-4 if bullet else units)
            lines.extend(['• '+wrapped[0]]+['  '+v for v in wrapped[1:]] if bullet else wrapped)
        limit = min(10,max(1,int(height*72/(22*1.2))-1))
        if len(lines)>limit:
            fail(f'Visible briefing text needs {len(lines)} lines; the selected composition allows {limit}')
        return lines

    caption_lines = wrap(caption,110) if visual and caption else []
    if len(caption_lines)>2:
        fail('The visible caption exceeds two lines; move detailed explanation to speaker_notes')
    if visual is None:
        lines = text_lines(11.7,4.8)
        slide = page(content['title'],content.get('source_notes',[]))
        if lines:
            textbox(slide,.8,1.6,11.7,4.8,lines,22)
        return stats

    if visual[0] == 'figure':
        box = (.8,1.55,7.6 if text else 11.7,4.7)
        lines = text_lines(3.8,4.7) if text else []
        slide = page(content['title'],content.get('source_notes',[]))
        _,data,width,height = visual
        x,y,w,h = box
        fitted_w,fitted_h = min(w,h*width/height),min(h,w*height/width)
        slide.shapes.add_picture(io.BytesIO(data),Inches(x+(w-fitted_w)/2),Inches(y+(h-fitted_h)/2),
                                 width=Inches(fitted_w),height=Inches(fitted_h))
        if lines:
            textbox(slide,8.7,1.6,3.8,4.7,lines,22)
    else:
        _,columns,rows = visual
        side = bool(text) and len(columns)<=4 and len(rows)<=7
        width = 7.8 if side else 11.7
        height = 4.7 if side or not text else 3.25
        unit_width = max(8,int((width/len(columns)-.16)*72/7))
        heights = [max(.36,max(len(wrap(v,unit_width)) for v in row)*14*1.2/72+.13)
                   for row in [columns,*rows]]
        if sum(heights)>height:
            fail(f'The briefing table needs {sum(heights):.2f} inches; its frame allows {height:.2f}')
        lines = text_lines(3.6 if side else 11.7,4.7 if side else 1.25) if text else []
        slide = page(content['title'],content.get('source_notes',[]))
        table = slide.shapes.add_table(len(rows)+1,len(columns),Inches(.8),Inches(1.65),
                                      Inches(width),Inches(sum(heights))).table
        for ri,values in enumerate([columns,*rows]):
            table.rows[ri].height = Inches(heights[ri])
            for ci,value in enumerate(values):
                cell = table.cell(ri,ci)
                cell.text = value
                cell.margin_left=cell.margin_right=Inches(.08)
                cell.margin_top=cell.margin_bottom=Inches(.05)
                cell.fill.solid()
                cell.fill.fore_color.rgb = title_color if ri==0 else RGBColor(*(243,247,247) if ri%2==0 else (255,255,255))
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.name='Noto Sans CJK SC'
                    paragraph.font.size=Pt(14)
                    paragraph.font.bold=ri==0
                    paragraph.font.color.rgb=RGBColor(255,255,255) if ri==0 else RGBColor(23,43,59)
        if lines:
            textbox(slide,8.9 if side else .8,1.6 if side else 5.15,3.6 if side else 11.7,
                    4.7 if side else 1.25,lines,22)
    if caption_lines:
        textbox(slide,.8,6.4,11.7,.4,caption_lines,12,RGBColor(82,103,116))
    return stats
