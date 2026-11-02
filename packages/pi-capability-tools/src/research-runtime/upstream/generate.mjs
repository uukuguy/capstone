// Reproducible, dependency-free TypeScript erasure. Pinned sources stay exact.
import {stripTypeScriptTypes} from 'node:module';
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const manifest=JSON.parse(readFileSync(new URL('./manifest.json',import.meta.url),'utf8'));
for(const [file,digest] of Object.entries(manifest.files)) {
  let source=readFileSync(new URL('./source/'+file,import.meta.url),'utf8');
  if(createHash('sha256').update(source).digest('hex')!==digest)throw new Error('Pinned upstream source changed: '+file);
  if(file==='state-machine.ts') {
    // Optional stage ports; the default original web-research methods remain.
    source=source.replace('this.searchFn = ctx.searchFn;', 'this.ports = ctx.ports;\n    this.searchFn = ctx.searchFn;');
    const hooks=[
      ['const prof = snapshot.profile!;\n    // Use plan research questions', "if (this.ports?.searching) return this.ports.searching(snapshot, plan);\n    const prof = snapshot.profile!;\n    // Use plan research questions"],
      ['const nextPhase = phaseRouter(snapshot);', 'if (this.ports?.extracting) return this.ports.extracting(snapshot, plan);\n    const nextPhase = phaseRouter(snapshot);'],
      ['if (parsedResponse) {\n      const questions', 'if (this.ports?.questioning) return this.ports.questioning(snapshot, plan, parsedResponse);\n    if (parsedResponse) {\n      const questions'],
      ['const reportText = parsedResponse ?? "";', 'if (this.ports?.drafting) return this.ports.drafting(snapshot, plan, parsedResponse);\n    const reportText = parsedResponse ?? "";'],
      ['if (!snapshot.draft.isReady()) {', 'if (this.ports?.saving) return this.ports.saving(snapshot, _parsedResponse);\n    if (!snapshot.draft.isReady()) {'],
      ['case "done":\n        return { phase: "done", snapshot };', 'case "done":\n        return { phase: "done", snapshot };\n      default:\n        throw new Error("Invalid research phase");'],
    ];
    for(const [oldText,newText] of hooks) {
      if(!source.includes(oldText))throw new Error('Upstream port patch no longer applies');
      source=source.replace(oldText,newText);
    }
  }
  const javascript=stripTypeScriptTypes(source,{mode:'transform'}).replaceAll(/(from\s+["'][^"']+)\.js(["'])/g,'$1.mjs$2');
  writeFileSync(new URL('./runtime/'+file.replace(/\.ts$/,'.mjs'),import.meta.url),
    '// Generated from pinned MIT source; see ../generate.mjs and ../../LICENSE.\n'+javascript);
}
