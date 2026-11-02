// Resolve identities only inside an explicit publication grant. No namespace
// strings, business names or provider names belong in this neutral index.
export function createToolIdentityResolver(publications,admittedNames=Object.keys(publications)){
  const identities=new Map();
  for(const registered of new Set(admittedNames)){
    if(!Object.hasOwn(publications,registered))continue;
    for(const identity of new Set([registered,publications[registered].name])){
      if(typeof identity!=='string'||!identity.length||identity.length>256)continue;
      const candidates=identities.get(identity)??new Set();
      candidates.add(registered);identities.set(identity,candidates);
    }
  }
  const display=names=>JSON.stringify(names.slice(0,8).map(name=>name.slice(0,128)));
  function resolveMany(names){
    if(!Array.isArray(names)||names.some(name=>typeof name!=='string'))
      throw new Error('Tool selection names must be an array of strings');
    const ambiguous=names.filter(name=>(identities.get(name)?.size??0)>1);
    if(ambiguous.length)throw new Error('Requested tool name is ambiguous in this task publication: '+display(ambiguous));
    const unknown=names.filter(name=>!identities.has(name));
    if(unknown.length)throw new Error('Requested tool is not admitted for this task: '+display(unknown));
    return names.map(name=>identities.get(name).values().next().value);
  }
  return {resolveMany,resolve:name=>resolveMany([name])[0]};
}
