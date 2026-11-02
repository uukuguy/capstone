import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm,realpath} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {prepareDeliveryReview,completeDeliveryReview,assertDeliveryReview,deliveryReviewStatus} from '../../src/capstone_agent/resources/delivery-review.mjs';

async function fixture(t){
  const root=await mkdtemp(join(tmpdir(),'delivery-review-'));t.after(()=>rm(root,{recursive:true,force:true}));
  await writeFile(join(root,'report.html'),'<html><style>private style</style><h1>Actual report</h1><p>Zero incidents.</p><figure><img src="data:image/png;base64,AAAA"><figcaption>Recorded image</figcaption></figure></html>');
  await writeFile(join(root,'metrics.csv'),'label,value\nincidents,2\n');
  return realpath(root);
}
const successful=packet=>({source:{id:'reviewer'},status:'completed',answer:JSON.stringify({summary:'The saved prose contradicts the saved table.',findings:[{severity:'blocking',path:'report.html',description:'Zero conflicts with incidents=2.'}],not_checked:[]})});

test('actual revision response with top-level text-only scope retains its findings',async()=>{
  const child=JSON.parse(await readFile(new URL('./delivery-review-revision-response.json',import.meta.url),'utf8'));
  const raw=JSON.parse(child.answer);assert.equal(raw.scope,'text_level_only');
  const paths=[...new Set(raw.findings.map(item=>item.path))];
  const packet={products:paths.map(path=>({path,sha256:'a'.repeat(64),bytes:10})),documents:[{path:paths[0],kind:'product',text:'Actual saved bytes',scope:'full_text'}],not_checked:[]};
  assert.equal(completeDeliveryReview(packet,[child]).findings.length,raw.findings.length);
});

test('actual completed review explanations stay in raw answers while only core findings enter control',async()=>{
  const responses=JSON.parse(await readFile(new URL('./delivery-review-live-responses.json',import.meta.url),'utf8'));
  assert.equal(responses.length,4);
  responses.push(JSON.parse(await readFile(new URL('./delivery-review-revision-response.json',import.meta.url),'utf8')));
  for(const child of responses){
    const original=child.answer;
    const raw=JSON.parse(child.answer),paths=[...new Set(raw.findings.map(item=>item.path))];
    const packet={products:paths.map(path=>({path,sha256:'a'.repeat(64),bytes:10})),documents:[{kind:'product',path:paths[0],text:'Actual saved text',scope:'full_text'}],not_checked:[]};
    const review=completeDeliveryReview(packet,[child]);assert.equal(review.findings.length,raw.findings.length);
    const core=raw.findings.map(({severity,path,description})=>({severity,path,description}));
    assert.deepEqual(review.findings.map(({id,...item})=>item),core);
    assert.equal(child.answer,original);
    const extra=structuredClone(raw);extra.ready=true;extra.grants=['write'];extra.scope='text_level_only';
    extra.products=[{path:'forged.txt',sha256:'b'.repeat(64)}];extra.receipts=[{status:'completed'}];
    extra.findings[0].severity_override='warning';extra.findings[0].source_ref='fabricated';extra.findings[0].path_note={nested:'ignored explanation'};
    const projected=completeDeliveryReview(packet,[{...child,answer:JSON.stringify(extra)}]);
    assert.deepEqual(projected.findings,review.findings,'metadata does not change finding IDs, severity, path or description');
    assert.ok(!Object.hasOwn(projected,'ready'));assert.ok(!Object.hasOwn(projected,'grants'));assert.ok(!Object.hasOwn(projected,'scope'));
    assert.deepEqual(projected.products,packet.products);assert.ok(!Object.hasOwn(projected,'receipts'));
  }
});

test('core review structure remains strict despite explanatory metadata tolerance',async t=>{
  const root=await fixture(t),packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:20000}});
  const valid={summary:'Read actual text',findings:[{severity:'blocking',path:'report.html',description:'Verify this discrepancy'}],not_checked:[]};
  const child={source:{id:'reviewer'},status:'completed',answer:''};
  const invalid=[null,[],{}, {...valid,summary:null},{...valid,summary:[]},{...valid,summary:''},
    {...valid,findings:null},{...valid,findings:{}},{...valid,not_checked:null},{...valid,not_checked:[{}]},
    ...[null,[],{}, {severity:'critical',path:'report.html',description:'Invalid severity'},
      {severity:'blocking',path:'outside.html',description:'Forged path'}, {severity:'blocking',path:'report.html',description:null},
      {severity:'blocking',path:['report.html'],description:'Wrong type'}].map(finding=>({...valid,findings:[finding]}))];
  for(const result of invalid)assert.throws(()=>completeDeliveryReview(packet,[{...child,answer:JSON.stringify(result)}]),/review/);
  assert.throws(()=>completeDeliveryReview(packet,[{...child,answer:'Not JSON'}]),/structured/);
  for(const status of ['failed','cancelled'])assert.throws(()=>completeDeliveryReview(packet,[{...child,status,answer:JSON.stringify(valid)}]),/failed|cancelled/);
});

test('current review packets can cover separate final files with explicit missing and stale diagnostics',async t=>{
  const root=await fixture(t);await writeFile(join(root,'process.py'),'source code');
  const packet=await prepareDeliveryReview(root,['report.html','metrics.csv','process.py'],{limits:{input_text_chars:20000}});
  const clean=products=>completeDeliveryReview({...packet,products},[{source:{id:'reviewer'},status:'completed',answer:JSON.stringify({summary:'Read current saved files',findings:[],not_checked:[]})}]);
  const final=packet.products.filter(item=>item.path!=='process.py');
  const receipts=[{status:'completed',ref:'report-review',review:clean(packet.products.filter(item=>item.path!=='metrics.csv'))},
    {status:'completed',ref:'metrics-review',review:clean(packet.products.filter(item=>item.path==='metrics.csv'))}];
  assert.doesNotThrow(()=>assertDeliveryReview(final,receipts,[],new Set(),packet.products));
  const missing=deliveryReviewStatus(final,receipts.slice(0,1),[],new Set(),packet.products);
  assert.deepEqual(missing.missing_products,['metrics.csv']);assert.equal(missing.ready,false);
  const changed=packet.products.map(item=>item.path==='process.py'?{...item,sha256:'b'.repeat(64)}:item);
  const stale=deliveryReviewStatus(final,receipts,[],new Set(),changed);
  assert.deepEqual(stale.missing_products,['report.html']);assert.equal(stale.stale_reviews[0].products[0].path,'process.py');
});

test('changing bundle scope or unrelated report bytes cannot erase an unresolved script finding',async t=>{
  const root=await fixture(t);await writeFile(join(root,'process.py'),'wrong script');
  const packet=await prepareDeliveryReview(root,['report.html','metrics.csv','process.py'],{limits:{input_text_chars:20000}});
  const child={source:{id:'reviewer'},status:'completed',answer:JSON.stringify({summary:'Script needs verification',findings:[{severity:'blocking',path:'process.py',description:'Verify the source units before changing a figure.'}],not_checked:[]})};
  const old=completeDeliveryReview(packet,[child]);
  const final=packet.products.filter(item=>item.path!=='process.py').map(item=>item.path==='report.html'?{...item,sha256:'b'.repeat(64)}:item);
  const clean=completeDeliveryReview({...packet,products:final},[{...child,answer:JSON.stringify({summary:'Current final text read',findings:[],not_checked:[]})}]);
  const receipts=[{status:'completed',ref:'old',review:old},{status:'completed',ref:'new',review:clean}],inspected=[...final,packet.products.find(item=>item.path==='process.py')];
  const status=deliveryReviewStatus(final,receipts,[],new Set(),inspected);
  assert.equal(status.blocking_findings[0].id,old.findings[0].id);
  assert.throws(()=>assertDeliveryReview(final,receipts,[],new Set(),inspected),/unhandled finding/);
  const renamed=final.map(item=>({...item,path:'renamed/'+item.path}));
  assert.equal(deliveryReviewStatus(renamed,receipts,[],new Set(),inspected).blocking_findings[0].id,old.findings[0].id,'renaming final outputs cannot discard retained blocking questions');
  assert.equal(deliveryReviewStatus(final.filter(item=>item.path==='metrics.csv'),receipts,[],new Set(),inspected).blocking_findings[0].id,old.findings[0].id,'excluding a promised report cannot evade a known supporting-script finding');
  assert.doesNotThrow(()=>assertDeliveryReview(final,receipts,[{id:old.findings[0].id,status:'refuted',text:'Original source units directly contradict the reviewer hypothesis.',refs:['material:original']}],new Set(['material:original']),inspected));
});

test('actual product text and CSV bind review, without claiming vision',async t=>{
  const root=await fixture(t);
  const packet=await prepareDeliveryReview(root,['report.html','metrics.csv'],{limits:{input_text_chars:20000}});
  assert.match(packet.documents.find(x=>x.path==='report.html').text,/Zero incidents/);
  assert.match(packet.documents.find(x=>x.path==='metrics.csv').text,/incidents,2/);
  assert.ok(!JSON.stringify(packet.documents).includes('base64,AAAA'));
  assert.ok(packet.not_checked.some(x=>/visual/i.test(x)));
  const review=completeDeliveryReview(packet,[successful(packet)]);
  assert.equal(review.findings.length,1);
  assert.ok(review.findings[0].id.startsWith('review-'));
  assert.throws(()=>assertDeliveryReview(packet.products,[],[]),/review/i,'a write/self-check is not a review');
  assert.throws(()=>assertDeliveryReview(packet.products,[{status:'completed',ref:'write'}],[]),/review/i);
  assert.throws(()=>assertDeliveryReview(packet.products,[{status:'completed',ref:'delegate',review}],[]),/finding/i);
  const refuted=[{id:review.findings[0].id,status:'refuted',text:'Original source evidence contradicts this reviewer.',refs:['material:original']}];
  assert.doesNotThrow(()=>assertDeliveryReview(packet.products,[{status:'completed',ref:'delegate',review}],refuted,new Set(['material:original'])));
  assert.throws(()=>assertDeliveryReview(packet.products,[{status:'completed',ref:'delegate',review}],refuted,new Set(['ls-result'])),/finding/i);
  const changedTable=packet.products.map(product=>product.path==='metrics.csv'?{...product,sha256:'b'.repeat(64)}:product);
  assert.throws(()=>assertDeliveryReview(changedTable,[{status:'completed',ref:'delegate',review}],refuted,new Set(['material:original'])),/current|version/i,'unchanged prose cannot reuse a review against changed supporting data');
  await writeFile(join(root,'report.html'),'<p>Revised report</p>');
  const changed=await prepareDeliveryReview(root,['report.html','metrics.csv'],{limits:{input_text_chars:20000}});
  assert.throws(()=>assertDeliveryReview(changed.products,[{status:'completed',ref:'delegate',review}],refuted,new Set(['material:original'])),/current|version/i);
});

test('cancelled, failed, nonstructured and empty review results are unavailable',async t=>{
  const root=await fixture(t);const packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:20000}});
  for(const child of [{...successful(packet),status:'cancelled'},{...successful(packet),status:'failed'},
    {...successful(packet),answer:'Everything passed.'}])assert.throws(()=>completeDeliveryReview(packet,[child]),/review/i);
  assert.throws(()=>completeDeliveryReview(packet,[]),/review/i);
});

test('blocking findings on review-only support files gate delivery of the saved bundle',async t=>{
  const root=await fixture(t);await writeFile(join(root,'process.py'),'total = sum(rows)\n');
  const packet=await prepareDeliveryReview(root,['report.html','metrics.csv','process.py'],{limits:{input_text_chars:20000}});
  const child={source:{id:'reviewer'},status:'completed',answer:JSON.stringify({summary:'Read report, metrics and producing script.',
    findings:[{severity:'blocking',path:'process.py',description:'The script aggregates incompatible units into the published total.'}],not_checked:[]})};
  const review=completeDeliveryReview(packet,[child]),receipts=[{status:'completed',ref:'review-receipt',review}];
  const active=packet.products.filter(product=>product.path!=='process.py');
  assert.throws(()=>assertDeliveryReview(active,receipts,[],new Set(),packet.products),/unhandled finding/);
  const refuted=[{id:review.findings[0].id,status:'refuted',text:'The admitted source defines these rows in the same unit.',refs:['material:original']}];
  assert.doesNotThrow(()=>assertDeliveryReview(active,receipts,refuted,new Set(['material:original']),packet.products));
  assert.throws(()=>assertDeliveryReview(active,receipts,refuted,new Set(['ls-result']),packet.products),/unhandled finding/);
  await writeFile(join(root,'process.py'),'total = sum(convert_units(rows))\n');
  const repaired=await prepareDeliveryReview(root,['report.html','metrics.csv','process.py'],{limits:{input_text_chars:20000}});
  assert.throws(()=>assertDeliveryReview(active,receipts,[],new Set(),repaired.products),/unhandled finding/);
  const rereview=completeDeliveryReview(repaired,[{...child,answer:JSON.stringify({summary:'Read the revised script and saved outputs.',findings:[],not_checked:[]})}]);
  assert.doesNotThrow(()=>assertDeliveryReview(active,[...receipts,{status:'completed',ref:'new-review',review:rereview}],[],new Set(),repaired.products));
});

test('authorized inputs are bounded with honest coverage and preserve exact source identity',async t=>{
  const root=await fixture(t);const source=join(root,'README.md');const bytes=Buffer.from('Units are samples; aggregate, not subtype. '.repeat(100));await writeFile(source,bytes);
  const packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:1200},sources:[{path:source,file_name:'README.md',sha256:createHash('sha256').update(bytes).digest('hex'),size_bytes:bytes.length,source_ref:'material:original',origin:'original_input'}]});
  assert.ok(packet.documents.some(x=>x.source_ref==='material:original'));
  assert.ok(packet.not_checked.some(x=>/excerpt|source/i.test(x)));
  assert.ok(packet.documents.reduce((n,d)=>n+Array.from(d.text).length,0)<=1200);
});

test('arbitrary product traversal or source hash substitution is rejected',async t=>{
  const root=await fixture(t);
  await assert.rejects(prepareDeliveryReview(root,['../report.html'],{limits:{input_text_chars:20000}}));
  await assert.rejects(prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:20000},sources:[{path:join(root,'metrics.csv'),file_name:'metrics.csv',sha256:'a'.repeat(64),size_bytes:24,source_ref:'material:original'}]}));
});

test('HTML scans beyond large embedded images and historical excerpts remain excerpts',async t=>{
  const root=await fixture(t);
  await writeFile(join(root,'large.html'),'<h1>Actual saved heading</h1><img src="data:image/png;base64,'+'A'.repeat(30000)+'"><p>Unseen tail</p>');
  const source=join(root,'history.html'),bytes=Buffer.from('<p>Prior supplied excerpt</p>');await writeFile(source,bytes);
  const packet=await prepareDeliveryReview(root,['large.html'],{limits:{input_text_chars:4000},sources:[{path:source,file_name:'history.html',sha256:createHash('sha256').update(bytes).digest('hex'),size_bytes:bytes.length,source_ref:'material:excerpt',excerpt:true}]});
  const product=packet.documents.find(doc=>doc.kind==='product');
  assert.equal(product.scope,'text_projection');assert.match(product.text,/Actual saved heading/);assert.match(product.text,/Unseen tail/);assert.ok(!product.text.includes('AAAA'));
  assert.equal(packet.documents.find(doc=>doc.source_ref==='material:excerpt').scope,'excerpt');
  assert.ok(packet.not_checked.some(text=>text.includes('complete original source')));
});

test('streamed HTML retains final prose past giant data URI and skips script, style and unclosed attributes',async t=>{
  const root=await fixture(t);
  const html='<h1>开头正文</h1><script>FORBIDDEN_SCRIPT '+ 'secretScript'.repeat(20000)+'</script>'+ '<style>FORBIDDEN_STYLE '+ 'styleData'.repeat(20000)+'</style>'+ '<img alt=">not a tag end" src="data:image/png;base64,'+'A'.repeat(1500000)+'"><h2>最后章节</h2><p>结论 &amp; 边界 &#x4e2d;文 😀</p>';
  await writeFile(join(root,'large.html'),html);
  const packet=await prepareDeliveryReview(root,['large.html'],{limits:{input_text_chars:4000}});
  const doc=packet.documents[0];assert.equal(doc.scope,'text_projection');assert.match(doc.text,/最后章节 结论 & 边界 中文 😀/);
  assert.ok(!/FORBIDDEN|AAAA|secretScript|styleData|base64/.test(doc.text));
  assert.equal(doc.sha256,createHash('sha256').update(html).digest('hex'));
  await writeFile(join(root,'large.html'),'<p>Visible</p><img src="data:image/png;base64,'+'A'.repeat(20000));
  const unclosed=await prepareDeliveryReview(root,['large.html'],{limits:{input_text_chars:4000}});
  assert.equal(unclosed.documents[0].text,'Visible');
  await writeFile(join(root,'large.html'),'<p>'+ 'visible '.repeat(10000)+'</p>');
  const bounded=await prepareDeliveryReview(root,['large.html'],{limits:{input_text_chars:4000}});
  assert.equal(bounded.documents[0].scope,'excerpt');assert.ok(Array.from(JSON.stringify(bounded)).length<=4000);
});

test('remaining source budget gives each large admitted CSV an excerpt after report and README',async t=>{
  const root=await fixture(t);const sources=[];
  for(const file of ['README.md','prices.csv','flows.csv','generation.csv']){
    const data=Buffer.from(file==='README.md'?'Actual source definitions and units.':'time,value\n'+('2026,'+file[0]+'\n').repeat(10000));
    const path=join(root,file);await writeFile(path,data);sources.push({path,file_name:file,size_bytes:data.length,sha256:createHash('sha256').update(data).digest('hex'),source_ref:'material:'+file});
  }
  const packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:12000},sources});
  const csvs=packet.documents.filter(doc=>doc.path.endsWith('.csv'));
  assert.equal(csvs.length,3);assert.ok(csvs.every(doc=>doc.text.length>0&&doc.scope==='excerpt'));
  assert.ok(Math.max(...csvs.map(doc=>doc.text.length))-Math.min(...csvs.map(doc=>doc.text.length))<=10);
  assert.equal(packet.documents.find(doc=>doc.path==='README.md').scope,'full_text');
  assert.equal(packet.documents.find(doc=>doc.path==='report.html').scope,'text_projection');
  assert.ok(Array.from(JSON.stringify(packet)).length<=12000);
});

test('review sources follow trusted role, explicit references and fixed configurable excerpt target',async t=>{
  const root=await fixture(t),sources=[];
  for(const [file_name,origin,text] of [['README.md','original_input','测'.repeat(1846)],['data.csv','original_input','x'.repeat(80000)],['old.py','previous_product','historical script'],['selected.txt','selected_context','selected version']]){
    const path=join(root,file_name);await writeFile(path,text);sources.push({path,file_name,origin,source_ref:'source:'+file_name,size_bytes:Buffer.byteLength(text),sha256:createHash('sha256').update(text).digest('hex')});
  }
  const packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:200000},sources});
  assert.deepEqual(packet.documents.filter(x=>x.kind==='source').map(x=>x.path).sort(),['README.md','data.csv','selected.txt']);
  assert.equal(packet.documents.find(x=>x.path==='data.csv').text.length,16384);
  assert.equal(packet.documents.find(x=>x.path==='README.md').scope,'full_text');
  assert.equal(Buffer.byteLength(packet.documents.find(x=>x.path==='README.md').text),5538);
  assert.equal(packet.source_selection.source_excerpt_chars,16384);
  assert.equal(packet.source_selection.excluded[0].source_ref,'source:old.py');
  assert.ok(packet.not_checked.some(x=>x.includes('historical sources excluded')));
  const selected=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:200000},sources,source_refs:['source:old.py'],source_excerpt_chars:30000});
  assert.notEqual(selected.fingerprint,packet.fingerprint);
  assert.ok(selected.documents.some(x=>x.path==='old.py'));assert.equal(selected.documents.find(x=>x.path==='data.csv').text.length,30000);
  await assert.rejects(prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:200000},sources,source_refs:['forged']}),/source/);
  for(const value of [0,-1,1.5])await assert.rejects(prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:200000},sources,source_excerpt_chars:value}),/excerpt/);
});

test('exact content dedup keeps aliases and products; unclassified legacy input is explicit',async t=>{
  const root=await fixture(t);const path=join(root,'metrics.csv'),data=await readFile(path);
  const source={path,file_name:'old-metrics.csv',size_bytes:data.length,sha256:createHash('sha256').update(data).digest('hex'),source_ref:'source:one',origin:'original_input'};
  const packet=await prepareDeliveryReview(root,['report.html','metrics.csv'],{limits:{input_text_chars:20000},sources:[source,{...source,file_name:'alias.csv',source_ref:'source:two'}]});
  assert.equal(packet.products.length,2);assert.equal(packet.documents.length,2);
  assert.deepEqual(packet.documents.find(x=>x.path==='metrics.csv').source_aliases.map(x=>x.source_ref),['source:one','source:two']);
  assert.match(packet.fingerprint,/^[a-f0-9]{64}$/);
  assert.equal((await prepareDeliveryReview(root,['report.html','metrics.csv'],{limits:{input_text_chars:20000},sources:[source,{...source,file_name:'alias.csv',source_ref:'source:two'}]})).fingerprint,packet.fingerprint);
  const legacy=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:20000},sources:[{...source,origin:undefined}]});
  assert.ok(legacy.documents.some(x=>x.kind==='source'));assert.ok(legacy.not_checked.some(x=>/legacy.*unclassified/i.test(x)));
});

test('content aliases do not confuse plain raw text with HTML projection; successful receipt retains source scope',async t=>{
  const root=await fixture(t),data=await readFile(join(root,'report.html'));
  await writeFile(join(root,'same.txt'),data);
  const source={path:join(root,'same.txt'),file_name:'same.txt',origin:'original_input',sha256:createHash('sha256').update(data).digest('hex'),size_bytes:data.length,source_ref:'source:same'};
  const packet=await prepareDeliveryReview(root,['report.html'],{limits:{input_text_chars:20000},sources:[source]});
  assert.equal(packet.documents.length,2);assert.deepEqual(packet.documents.map(x=>x.projection),['markup_text','plain_text']);
  const receipt=completeDeliveryReview(packet,[successful(packet)]);
  assert.deepEqual(receipt.source_selection,packet.source_selection);assert.equal(receipt.packet_fingerprint,packet.fingerprint);
  const {reviewPrompt}=await import('../../src/capstone_agent/resources/delivery-review.mjs');
  assert.match(reviewPrompt(packet),/factual, numerical, definition, unit or coverage contradictions are blocking/);
  assert.match(reviewPrompt(packet),/style suggestions are warnings/);
});
