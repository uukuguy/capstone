"""Exact historical row selections over admitted immutable result projections."""
from hashlib import sha256
import json
import re

SCHEMA = 'capstone-result-row-selection/1'


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def identity(value):
    return sha256(encoded(value)).hexdigest()


def checked_ids(values, maximum):
    if (not isinstance(values, list) or not 1 <= len(values) <= maximum
            or any(not isinstance(v, str) or not v or len(v) > 128 for v in values)
            or len(set(values)) != len(values)):
        raise ValueError('invalid result row or column selection')
    return values


def checked_row_selection(value):
    from .thread_products import checked_ref
    if not isinstance(value, dict) or set(value) != {'schema','parent_ref','table_id','table_version','row_ids','column_ids','digest'}:
        raise ValueError('invalid row selection fields')
    if value['schema'] != SCHEMA or checked_ref(value['parent_ref'])['origin'] != 'domain_result':
        raise ValueError('invalid row selection parent')
    if not isinstance(value['table_id'], str) or not re.fullmatch('[a-z][a-z0-9_.:-]{0,127}',value['table_id']):
        raise ValueError('invalid result table identity')
    for key in ('table_version','digest'):
        if not isinstance(value[key], str) or not re.fullmatch('[a-f0-9]{64}',value[key]):
            raise ValueError('invalid row selection digest')
    checked_ids(value['row_ids'],128)
    checked_ids(value['column_ids'],64)
    if value['row_ids'] != sorted(value['row_ids']):
        raise ValueError('row identities must be normalized')
    return value


def table_version(projection, table):
    return identity({'projection': projection.to_document(), 'table':table.to_document()})


def selected_document(projection, selection, store, *, verify=True):
    table = next(t for t in projection.tables if t.table_id == selection['table_id'])
    rows = checked_ids(selection['row_ids'],128)
    columns = checked_ids(selection['column_ids'],64)
    selected_columns = [c.to_document() for c in table.columns if c.column_id in columns]
    if columns != [c['column_id'] for c in selected_columns]:
        raise ValueError('unknown or noncanonical result columns')
    if selection['table_version'] != table_version(projection,table):
        raise ValueError('result table version changed')
    if table.pagination:
        source = store.selected_rows(projection,table.table_id,table.pagination.manifest_ref,rows)
    else:
        indexed = {r.row_id:r.to_document() for r in table.rows}
        if any(r not in indexed for r in rows):
            raise ValueError('unknown result row')
        source = [indexed[r] for r in rows]
    document = {'parent_ref': selection['parent_ref'],'table_id':table.table_id,
        'table_version':selection['table_version'],'title':table.title,'columns':selected_columns,
        'rows':[{'row_id':r['row_id'],'cells':{c:r['cells'].get(c) for c in columns},
                 **({'element_ref':r['element_ref']} if 'element_ref' in r else {})} for r in source]}
    if len(encoded(document)) > 24*1024:
        raise ValueError('selected result exceeds context budget')
    if verify and selection['digest'] != identity(document):
        raise ValueError('selected result digest mismatch')
    return document


def prepare_selection(projection, ref, table_id, row_ids, column_ids, store):
    checked_ids(row_ids,128)
    checked_ids(column_ids,64)
    table = next(t for t in projection.tables if t.table_id == table_id)
    canonical = [c.column_id for c in table.columns if c.column_id in column_ids]
    if len(canonical) != len(column_ids):
        raise ValueError('unknown result column')
    selection = {'schema':SCHEMA,'parent_ref':ref,'table_id':table_id,
        'table_version':table_version(projection,table),'row_ids':sorted(row_ids),'column_ids':canonical}
    selection['digest'] = identity(selected_document(projection,selection,store,verify=False))
    return selection


def read_table_page(projection, ref, table_id, store, *, offset=0, limit=32):
    """Publish saved admitted inline tables as immutable pages, then read one page."""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 128:
        raise ValueError('invalid result table page bounds')
    table = next(t for t in projection.tables if t.table_id == table_id)
    if table.pagination:
        if limit != table.pagination.page_size:
            raise ValueError('use the published result table page size')
        page = store.read(projection,table_id,table.pagination.manifest_ref,offset=offset,max_bytes=256*1024)
        document = page['table']
        total, following = page['total_rows'],page['next_offset']
    else:
        total = len(table.rows)
        if offset > total or (offset == total and total != 0) or offset % limit:
            raise ValueError('result table offset is unavailable')
        page = store.inline_page(projection,table,offset=offset,limit=limit,
            version=table_version(projection,table))
        document, following = page['table'],page['next_offset']
    return {'schema':'capstone-result-row-page/1','parent_ref':ref,
        'table_version':table_version(projection,table),'table':document,
        'total_rows':total,'offset':offset,'next_offset':following}
