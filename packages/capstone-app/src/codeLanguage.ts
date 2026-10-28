const extensions:Record<string,string>={sql:'sql',py:'python',pyw:'python',js:'javascript',mjs:'javascript',cjs:'javascript',jsx:'javascript',ts:'typescript',tsx:'typescript',json:'json',jsonl:'json',yaml:'yaml',yml:'yaml',toml:'ini',ini:'ini',conf:'ini',sh:'bash',bash:'bash',zsh:'bash',ps1:'powershell',bat:'dos',cmd:'dos',c:'c',h:'c',cpp:'cpp',cc:'cpp',cxx:'cpp',hpp:'cpp',cs:'csharp',java:'java',go:'go',rs:'rust',rb:'ruby',php:'php',swift:'swift',kt:'kotlin',kts:'kotlin',scala:'scala',r:'r',jl:'julia',lua:'lua',pl:'perl',pm:'perl',dart:'dart',vue:'xml',svelte:'xml',css:'css',scss:'scss',less:'less',xml:'xml',properties:'properties',cmake:'cmake',diff:'diff',patch:'diff',tex:'latex',ex:'elixir',exs:'elixir',erl:'erlang',hs:'haskell',fs:'fsharp',vb:'vbnet',vhdl:'vhdl',v:'verilog',sv:'verilog'}
export function codeLanguage(name:string,media?:string|null){
  const base=name.split('/').at(-1)?.toLowerCase()??''
  if(base==='dockerfile'||base.startsWith('dockerfile.'))return 'dockerfile'
  if(base==='makefile'||base==='gnumakefile')return 'makefile'
  return extensions[base.split('.').at(-1)??'']??(media?.split(';')[0].trim()==='application/sql'?'sql':undefined)
}
