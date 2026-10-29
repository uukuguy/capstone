/** Parse CSV records before escaping cells for a literal GFM table preview. */
export function csvMarkdown(text:string){
  const rows:string[][]=[];let row:string[]=[],cell='',quoted=false;
  const input=text.replace(/^\uFEFF/,'');
  for(let i=0;i<input.length;i++){
    const c=input[i];
    if(c==='"'){
      if(quoted&&input[i+1]==='"'){cell+='"';i++}
      else if(quoted||cell==='')quoted=!quoted;
      else cell+=c;
    }else if(!quoted&&(c===','||c==='\n'||c==='\r')){
      row.push(cell);cell='';
      if(c!==','){rows.push(row);row=[];if(c==='\r'&&input[i+1]==='\n')i++}
    }else cell+=c;
  }
  if(cell!==''||row.length){row.push(cell);rows.push(row)}
  if(!rows.length)return {markdown:'',truncated:false};
  const width=rows.reduce((width,r)=>Math.min(100,Math.max(width,r.length)),0);
  const escape=(v:string)=>Array.from(v,c=>/[\p{P}\p{S}&\r\n]/u.test(c)?`&#${c.codePointAt(0)};`:c).join('');
  const line=(r:string[])=>'| '+Array.from({length:width},(_,i)=>escape(r[i]??'')).join(' | ')+' |';
  return {markdown:[line(rows[0]),'| '+Array(width).fill('---').join(' | ')+' |',...rows.slice(1,501).map(line)].join('\n'),
    truncated:rows.length>501||rows.some(r=>r.length>100)};
}
