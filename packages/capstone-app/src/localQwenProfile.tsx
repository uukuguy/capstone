export function isLocalQwenProfile(profile?: {id:string;icon?:string}) {
  return profile?.icon === 'qwen' || profile?.id === 'local-qwen-35b'
}

export function LocalQwenIcon() {
  return <img src="/icons/qwen.svg" alt="" aria-hidden="true"/>
}
