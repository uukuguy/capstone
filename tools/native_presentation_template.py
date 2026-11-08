"""Load a confined template and retain its masters without publishing sample slides."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree
from pathlib import Path


def load_template(workspace, selection, error):
    from pptx import Presentation
    from pptx.oxml.ns import qn
    builtin = selection == {'id': 'state-grid'}
    if builtin:
        raw = (Path(__file__).parent / 'presentation-templates/state-grid.pptx').read_bytes()
        selection = {'path': 'builtin:state-grid'}
    elif (not isinstance(selection, dict) or set(selection) - {'path', 'cover_slide', 'content_layout'}
            or not isinstance(selection.get('path'), str) or not selection['path'].lower().endswith('.pptx')):
        raise error('template requires a workspace PPTX path')
    else:
        raw = workspace.read(selection['path'], location='template.path', maximum=64 * 1024 * 1024)
    try:
        with ZipFile(BytesIO(raw)) as archive:
            if len(archive.infolist()) > 4096 or sum(item.file_size for item in archive.infolist()) > 256 * 1024 * 1024:
                raise error('template exceeds the processing budget')
            for name in archive.namelist():
                if 'vbaproject' in name.lower() or '/embeddings/' in name.lower():
                    raise error('template macros and embedded executable objects are unsupported')
                if name.endswith('.rels'):
                    relationships = ElementTree.fromstring(archive.read(name))
                    if any(item.get('TargetMode', '').lower() == 'external' for item in relationships):
                        raise error('template external relationships are unsupported')
        deck = Presentation(BytesIO(raw))
    except (BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise error('template is not a valid PPTX package') from exc
    # The existing content renderer owns a 16:9 layout. Reject other ratios
    # instead of stretching a brand template or clipping content silently.
    if abs(deck.slide_width / deck.slide_height - 16 / 9) > .002:
        raise error('template must use a 16:9 slide layout')
    cover_number = selection.get('cover_slide', 1)
    if type(cover_number) is not int or not 1 <= cover_number <= len(deck.slides):
        raise error('template cover_slide is outside the template')
    layout_number = selection.get('content_layout')
    if layout_number is not None:
        if type(layout_number) is not int or not 0 <= layout_number < len(deck.slide_layouts):
            raise error('template content_layout is outside the template')
        layout = deck.slide_layouts[layout_number]
    else:
        layout = min(deck.slide_layouts, key=lambda item: len(item.placeholders))
    cover = deck.slides[cover_number - 1]
    cover_color = '172B3B'
    for node in cover._element.iter(qn('a:rPr')):
        color = node.find('.//' + qn('a:srgbClr'))
        if color is not None:
            cover_color = color.get('val', cover_color)
            break
    cover_layout = cover.slide_layout
    pictures = []
    for shape in cover.shapes:
        # Cover pictures are brand artwork. Text and diagram groups are sample
        # content; do not copy them over newly generated content.
        if shape.shape_type == 13:
            pictures.append((deepcopy(shape.element), cover.part))
    background = deepcopy(cover._element.cSld.bg)
    for entry in list(deck.slides._sldIdLst):
        deck.part.drop_rel(entry.rId)
        deck.slides._sldIdLst.remove(entry)

    def page(is_cover):
        slide = deck.slides.add_slide(cover_layout if is_cover else layout)
        for shape in list(slide.shapes):
            slide.shapes._spTree.remove(shape.element)
        if is_cover:
            if background is not None:
                slide._element.cSld.insert(0, deepcopy(background))
            for element, source in pictures:
                element = deepcopy(element)
                for node in element.iter():
                    for attr in (qn('r:embed'), qn('r:link')):
                        if node.get(attr):
                            relation = source.rels[node.get(attr)]
                            node.set(attr, slide.part.relate_to(relation.target_part, relation.reltype))
                slide.shapes._spTree.insert_element_before(element, 'p:extLst')
        return slide

    return deck, page, {**({'id': 'state-grid'} if builtin else {'path': selection['path']}), 'sha256': sha256(raw).hexdigest(),
                        'cover_text_rgb': cover_color,
                        'cover_slide': cover_number, 'content_layout': list(deck.slide_layouts).index(layout)}
