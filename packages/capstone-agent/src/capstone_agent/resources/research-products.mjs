import {constants,readFileSync} from 'node:fs';
import {open,realpath} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {isAbsolute,resolve,relative,sep,extname} from 'node:path';
const pathPolicy=JSON.parse(readFileSync(new URL('./product-path-policy.json',import.meta.url),'utf8'));

/** Inspect saved bytes in the private workspace. This proves file presence and
 * identity only; enterprise checks and the host still own quality and admission.
 * Hash streams avoid loading large user products into model context or memory.
 */
export async function inspectResearchProducts(workspace,declared,{signal}={}) {
  const root=await realpath(workspace);
  const products=[],limitations=[];
  if(!Array.isArray(declared))throw new TypeError('Product declarations must be an array');
  const seen=new Set();
  for(const item of declared) {
    signal?.throwIfAborted();
    const name=item?.path;
    if(typeof name!=='string'||!name||isAbsolute(name)||
        !['primary','support','reproduction'].includes(item.role)||seen.has(name)) {
      limitations.push('Invalid or duplicate product declaration.');continue;
    }
    seen.add(name);
    const path=resolve(root,name),local=relative(root,path);
    const parts=local.split(sep);
    if(parts.some(part=>(pathPolicy.exclude_hidden_parts&&part.startsWith('.'))||pathPolicy.excluded_parts.includes(part))||
      pathPolicy.excluded_suffixes.includes(extname(local).toLowerCase())||pathPolicy.excluded_roots.includes(parts[0])) {
      limitations.push(`Product ${name} is a private or excluded runtime file; save the requested output to a publishable workspace path.`);continue;
    }
    if(!local||local==='..'||local.startsWith('..'+sep)||isAbsolute(local)) {
      limitations.push('Product path is outside the task workspace.');continue;
    }
    let handle;
    try {
      // Reject symlinked parents as well as symlinked leaf files.
      if(await realpath(path)!==path)throw new Error('unsafe_product');
      handle=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW);
      const before=await handle.stat({bigint:true});
      if(!before.isFile()||before.size===0n)throw new Error('empty_product');
      const hash=createHash('sha256');
      for await(const chunk of handle.createReadStream({autoClose:false})) {
        signal?.throwIfAborted();hash.update(chunk);
      }
      const after=await handle.stat({bigint:true});
      const named=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW);
      let current;
      try {current=await named.stat({bigint:true});}finally {await named.close();}
      const identity=stat=>[stat.dev,stat.ino,stat.size,stat.mtimeNs,stat.ctimeNs].join(':');
      if(identity(before)!==identity(after)||identity(after)!==identity(current)||await realpath(path)!==path)
        throw new Error('changed_product');
      products.push({path:name,role:item.role,bytes:Number(after.size),sha256:hash.digest('hex')});
    } catch(error) {
      signal?.throwIfAborted();
      limitations.push(`Product ${name} is missing, empty, changed during inspection, or is not a regular workspace file.`);
    } finally {await handle?.close();}
  }
  if(!products.some(item=>item.role==='primary'))limitations.push('No saved primary product is available.');
  return {ready:limitations.length===0,products,limitations};
}
