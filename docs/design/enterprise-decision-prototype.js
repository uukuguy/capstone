// Design fixtures only. No model, solver, authority or control-system connection.
(() => {
  const style = document.createElement('style');
  style.textContent = `
    .decision .paper{max-width:none;padding:24px;border:0;background:transparent}
    .decision .paperarea{padding:0;background:#f0f3eb}
    .decision-head{display:flex;justify-content:space-between;gap:16px;align-items:start}
    .decision-head h2{margin:12px 0!important;font-size:24px!important}
    .fixture-label{color:#775727;border:1px solid #cebd9d;padding:5px 8px;font-size:11px;white-space:nowrap}
    .scenario-controls{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}
    .scenario-controls button{padding:0 12px;border:1px solid #c5d0bc;border-radius:4px;font-size:12px;background:#fff}
    .scenario-controls button[aria-pressed=true]{background:#294b39;color:#fff;border-color:#294b39}
    .identity-strip{display:flex;flex-wrap:wrap;gap:8px 18px;padding:12px 0;border-top:1px solid #cbd5c2;border-bottom:1px solid #cbd5c2;font-size:11px;color:#50624b}
    .decision-card{border:1px solid #d1dac9;background:#fbfcf7;padding:18px;margin:16px 0}
    .decision-card h3{margin:0 0 12px!important;font-size:13px!important}
    .decision-card svg{display:block;width:100%;height:auto}
    .decision-caption{font-size:11px;line-height:1.7;color:#5f6e57;margin:10px 0 0}
    .decision-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#d2dbc9;border:1px solid #d2dbc9;margin:16px 0}
    .decision-metrics div{padding:15px 12px;background:#fbfcf7;font-size:11px;color:#607055}
    .decision-metrics strong{display:block;font:26px Georgia,serif;color:#2b4534;margin:7px 0}
    .decision-scroll{overflow:auto}.decision-scroll table{min-width:440px}
    .decision-note{padding:12px 15px;border-left:3px solid #a37c40;background:#f6eddd;font-size:12px;line-height:1.8;margin:14px 0}
    .decision-checks{list-style:none;padding:0;margin:0}.decision-checks li{display:flex;justify-content:space-between;gap:18px;padding:13px 0;border-bottom:1px solid #dae0d1;font-size:12px;line-height:1.7}
    .decision-checks b{font-weight:500;text-align:right}.decision-checks small{display:block;color:#6a755f}
    #recordedTopology{height:420px;background:white;border:1px solid #d1dac9;overflow:hidden}#recordedTopology svg{width:100%;height:100%;touch-action:none;cursor:grab}#recordedTopology svg:active{cursor:grabbing}\n    .decision .artifactbar{flex-wrap:wrap}.decision .tabs{gap:16px}
    .decision #version,.decision #versionUpdate{display:none}
    @media(max-width:900px){.decision .paper{padding:18px}.decision-metrics strong{font-size:22px}.decision-head{flex-wrap:wrap}.decision .artifacttools{margin-left:auto}}
  `;
  document.head.append(style);

  const cases = {
    fault: {name:'故障后', load:[124,109,83], volts:[1.01,.932,.974,1.018], adjust:'—', shed:'—', status:'示意：发现越限'},
    a: {name:'候选 A', load:[96,92,79], volts:[1.01,.947,.983,1.016], adjust:'80', shed:'0', status:'示意：电压复核未通过'},
    b: {name:'候选 B', load:[91,88,75], volts:[1.01,.964,.991,1.013], adjust:'100', shed:'12', status:'示意：所列检查通过'},
  };
  function state() {
    const s=current();
    if(!Object.hasOwn(cases,s.decisionCase))s.decisionCase='fault';
    if(![1,2].includes(s.decisionRevision))s.decisionRevision=1;
    return s;
  }
  const svgStart = (title,h=270) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 ${h}" role="img" aria-label="${title}，全部数值为合成示意"><rect width="560" height="${h}" fill="#fbfcf7"/>`;
  let topologyAsset;
  function network() {
    return '<div class="scenario-controls"><button id="topologyZoomIn">放大拓扑</button><button id="topologyZoomOut">缩小拓扑</button><button id="topologyFit">适配全图</button></div><div id="recordedTopology" tabindex="0" aria-label="IEEE-39拓扑画布，方向键平移，加减键缩放"><p>正在加载已记录的电气拓扑…</p></div><p id="topologyElement" class="decision-caption" aria-live="polite">悬停查看元件名称 · 拖动或方向键平移</p>';
  }
  async function mountTopology() {
    const mount=$('recordedTopology');if(!mount)return;
    try {
      topologyAsset ??= fetch('ieee39-recorded-topology.svg').then(r=>{if(!r.ok)throw Error('asset');return r.text()}).catch(e=>{topologyAsset=null;throw e});
      const markup=await topologyAsset;if(!mount.isConnected)return;
      mount.innerHTML=markup;
      const svg=mount.querySelector('svg'),full=[215,45,490,520];let box=[...full],drag=null;
      const draw=()=>svg.setAttribute('viewBox',box.join(' '));
      const zoom=f=>{const w=Math.max(100,Math.min(1600,box[2]*f)),h=w*full[3]/full[2];box=[box[0]+(box[2]-w)/2,box[1]+(box[3]-h)/2,w,h];draw()};
      $('topologyZoomIn').onclick=()=>zoom(.8);$('topologyZoomOut').onclick=()=>zoom(1.25);
      $('topologyFit').onclick=()=>{box=[...full];draw()};
      mount.onkeydown=e=>{if(['+','=','-','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key)){e.preventDefault();if(e.key==='+'||e.key==='=')zoom(.8);else if(e.key==='-')zoom(1.25);else if(e.key==='Home'){box=[...full];draw()}else{box[0]+=(e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0)*box[2]*.1;box[1]+=(e.key==='ArrowDown'?1:e.key==='ArrowUp'?-1:0)*box[3]*.1;draw()}}};
      const point=e=>new DOMPoint(e.clientX,e.clientY).matrixTransform(svg.getScreenCTM().inverse());
      svg.onpointerdown=e=>{if(e.button!==0)return;mount.focus();drag=point(e);svg.setPointerCapture(e.pointerId)};
      svg.onpointermove=e=>{if(drag){const p=point(e);box[0]+=drag.x-p.x;box[1]+=drag.y-p.y;draw()}else{const name=e.target.closest('g')?.querySelector('title')?.textContent;if(name)$('topologyElement').textContent=name+' · 已记录拓扑元件，无当前运行数值'}};
      svg.onpointerup=svg.onpointercancel=()=>{drag=null};
      draw();
    } catch {if(mount.isConnected)mount.textContent='拓扑资源未能加载。请刷新重试；不会用示意网络替代。'}
  }
  function loadChart(c) {
    const x=v=>90+v*3;
    return svgStart('线路负载率对比',245)+[0,50,100,150].map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="24" y2="190" stroke="${v===100?'#9e6743':'#e0e6d8'}" stroke-dasharray="${v===100?'5 4':'0'}"/><text x="${x(v)}" y="210" text-anchor="middle" font-size="11" fill="#617157">${v}%</text>`).join('')+c.load.map((v,i)=>`<text x="15" y="${51+i*54}" font-size="12" fill="#3c5134">线路 ${i+1}</text><rect x="90" y="${31+i*54}" width="${cases.fault.load[i]*3}" height="9" fill="#ccd4c2"/><rect x="90" y="${44+i*54}" width="${v*3}" height="14" fill="${v>100?'#ac6149':'#486f52'}"/><text x="${x(v)+6}" y="${56+i*54}" font-size="11" fill="#34482e">${v}</text>`).join('')+`<text x="16" y="235" font-size="10" fill="#6a735c">灰条：故障后　实条：当前选择　虚线：示意热限额100% · 合成数据</text></svg>`;
  }
  function voltageChart(c) {
    const y=v=>190-(v-.90)*1000;
    return svgStart('节点电压与约束范围',245)+`<rect x="65" y="${y(1.05)}" width="435" height="100" fill="#e6eddf"/>`+[.90,.95,1,1.05].map(v=>`<line x1="65" x2="500" y1="${y(v)}" y2="${y(v)}" stroke="#b6c6aa" stroke-dasharray="4 4"/><text x="48" y="${y(v)+4}" text-anchor="end" font-size="11" fill="#617157">${v.toFixed(2)}</text>`).join('')+c.volts.map((v,i)=>`<circle cx="${100+i*120}" cy="${y(v)}" r="5" fill="${v<.95||v>1.05?'#ad533c':'#3c674b'}"/><text x="${100+i*120}" y="${y(v)-12}" text-anchor="middle" font-size="12" fill="#34482e">${v.toFixed(3)}</text><text x="${100+i*120}" y="210" text-anchor="middle" font-size="12" fill="#617157">${'ABCD'[i]}</text>`).join('')+`<text x="16" y="20" font-size="11" fill="#617157">电压 / p.u.　阴影：0.95–1.05约束区间</text><text x="16" y="235" font-size="10" fill="#6a735c">节点为离散对象，不以连线暗示空间关系 · 合成数据，非AC复核</text></svg>`;
  }
  function header(s,c) {
    return `<div class="decision-head"><div><div class="overline">SCENARIO LAB / 001</div><h2>联络线退出后的运行边界</h2></div><span class="fixture-label">拓扑已记录 · 分析为合成示意</span></div><div class="identity-strip"><span>示意模型 M-01</span><span>示意快照 S-01</span><span>约束修订 r${s.decisionRevision}</span><span>当前：${c.name}</span></div><div class="scenario-controls" aria-label="查看场景或候选方案">${Object.entries(cases).map(([id,v])=>`<button data-case="${id}" aria-pressed="${id===s.decisionCase}">${v.name}</button>`).join('')}<button id="changeConstraint">${s.decisionRevision===1?'演示：改为禁止切负荷':'恢复原始示意约束'}</button></div><div class="decision-note" role="status">${s.decisionRevision===2?'约束已变更为禁止切负荷。所有旧结果属于 r1，当前只供比较，待重新计算与验证。':c.status+'。此处仅演示结果呈现，不是实际求解或可执行调度建议。'}</div>`;
  }
  function comparison() {
    return `<div class="decision-card"><h3>候选方案 · 同一快照下比较</h3><div class="decision-scroll"><table class="datatable"><thead><tr><th>方案</th><th>调整量¹ / MW</th><th>切负荷 / MW</th><th>示意检查</th></tr></thead><tbody><tr><td>A</td><td>80</td><td>0</td><td>电压未通过</td></tr><tr><td>B</td><td>100</td><td>12</td><td>所列检查通过</td></tr></tbody></table></div><p class="decision-caption">¹ 机组有功调整绝对值之和。没有逐机组方案或功率平衡计算，不可执行。没有成本和最优性证明，不标注“最优”。</p></div>`;
  }
  function checks(s,c) {
    const stale=s.decisionRevision===2;
    const rows=[['输入一致性','示意模型 M-01 / 快照 S-01；无真实数据'],['线路热限额',c.load.some(v=>v>100)?'示意：未通过':'示意：所列线路通过'],['节点电压',c.volts.some(v=>v<.95||v>1.05)?'示意：未通过':'示意：所列节点通过'],['功率平衡与收敛','未计算'],['机组及负荷调节边界','未校验'],['独立 AC 复核','无验证执行，无结果引用'],['最优性','未证明']];
    return `<div class="decision-card"><h3>验证记录 / ${c.name}</h3><ul class="decision-checks">${rows.map(([a,b])=>`<li><span>${a}</span><b>${b}${stale?'<small>旧约束 r1 · 当前已失效</small>':''}</b></li>`).join('')}</ul></div><div class="decision-card"><h3>来源与版本</h3><p>来源：设计文件内置合成数组。示意绑定：M-01 / S-01 / 故障 B–D / ${c.name} / r1。没有 Authority、run、result 或 evidence 引用。</p><p>正式运行中，验证必须指向同一候选方案修订；计算失败、无可行解、验证未通过和旧结果失效分别显示。只展示求解状态与可公开的验证依据，不展示模型内部思维链。</p></div>`;
  }
  function decisionPaper() {
    const s=state(),c=cases[s.decisionCase];
    let body;
    if(tab==='basis')body=checks(s,c);
    else if(tab==='chart')body=`<div class="decision-card"><h3>线路负载率 / ${c.name}</h3>${loadChart(c)}</div><div class="decision-card"><h3>节点电压 / ${c.name}</h3>${voltageChart(c)}</div><div class="scenario-controls"><button id="exportDecision">导出当前示意图 SVG</button></div><details class="decision-card"><summary>查看合成数据与口径</summary><p>负载率示意值按同一100%限额比较；节点电压单位p.u.。所有样本由界面内置，无潮流求解。</p><pre>${JSON.stringify({load:c.load,voltage:c.volts},null,2)}</pre></details>`;
    else body=`<div class="decision-card"><h3>电气拓扑图 / IEEE-39</h3>${network()}<p class="decision-caption">复用现有 NetworkView 的电气符号与模型坐标：39 母线 / 46 支路，来源 gridctl 已记录拓扑。此图未绑定当前候选方案；下方合成指标不映射到该模型。</p></div><div class="decision-metrics"><div>越限线路（示意）<strong>${c.load.filter(v=>v>100).length}</strong>仅含3条合成线路，非IEEE-39结果</div><div>最低电压（示意）<strong>${Math.min(...c.volts).toFixed(3)}</strong>p.u. / 4个示意节点</div><div>切负荷（示意）<strong>${c.shed}</strong>MW / 未生成调度指令</div></div>${comparison()}<div class="scenario-controls"><button data-decision-tab="chart">查看影响图表</button><button data-decision-tab="basis">检查验证依据</button></div>`;
    $('artifactContent').innerHTML=`<div class="paper">${header(s,c)}${body}<div class="docfooter"><span>DESIGN FIXTURE / NO SOLVER</span><span>无正式结果或证据</span></div></div>`;
    $('artifactStatus').textContent=s.decisionRevision===2?'示意约束已变更 · 旧结果待重新验证':'合成场景 · 非真实计算与调度建议';
    mountTopology();
    document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>{s.decisionCase=b.dataset.case;decisionPaper();document.querySelector(`[data-case="${s.decisionCase}"]`).focus();persistPrototype()});
    $('changeConstraint').onclick=()=>{s.decisionRevision=s.decisionRevision===1?2:1;decisionPaper();$('changeConstraint').focus();persistPrototype()};
    document.querySelectorAll('[data-decision-tab]').forEach(b=>b.onclick=()=>$('tab'+b.dataset.decisionTab).click());
    if($('exportDecision'))$('exportDecision').onclick=()=>{
      const svg=voltageChart(c).replace('</svg>',`<text x="350" y="20" font-size="10" fill="#805638">${c.name} / r1${s.decisionRevision===2?' / 已失效':''}</text></svg>`);
      const u=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));const a=document.createElement('a');a.href=u;a.download=`synthetic-voltage-${s.decisionCase}-r1.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);
    };
  }
  const previousPaper=paper;
  paper=function(){if(current().kind==='decision')decisionPaper();else previousPaper()};
  const previousRender=render;
  render=function(){previousRender();const d=current().kind==='decision';$('tabmain').textContent=d?'场景与方案':'报告';$('tabchart').textContent=d?'影响图表':'图表';$('tabbasis').textContent=d?'验证依据':'依据';};
})();
