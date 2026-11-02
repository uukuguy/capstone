import type {SceneCamera} from './networkScene'

/** Layout distances describe the published graph only, never geography or electrical islands. */
export function layoutSourceTopology(count:number,endpoints:Uint32Array,bounds:SceneCamera):Float32Array{
  if(count>800)throw new Error('Regional graph-distance layout is bounded to800 source nodes')
  const neighbors=Array.from({length:count},()=>new Set<number>())
  for(let e=0;e<endpoints.length;e+=2){const a=endpoints[e],b=endpoints[e+1];if(a!==b){neighbors[a].add(b);neighbors[b].add(a)}}
  const seen=new Uint8Array(count),components:number[][]=[]
  for(let start=0;start<count;start++)if(!seen[start]){
    const queue=[start];seen[start]=1
    for(let i=0;i<queue.length;i++)for(const next of neighbors[queue[i]])if(!seen[next]){seen[next]=1;queue.push(next)}
    components.push(queue)
  }
  components.sort((a,b)=>b.length-a.length||a[0]-b[0])
  const positions=new Float32Array(count*2)
  type Rect={x:number;y:number;width:number;height:number}
  function place(nodes:number[],rect:Rect){
    const n=nodes.length
    if(n===1){positions[nodes[0]*2]=rect.x+rect.width/2;positions[nodes[0]*2+1]=rect.y+rect.height/2;return}
    const local=new Map(nodes.map((id,i)=>[id,i])),distances=new Uint16Array(n*n),queue=new Uint16Array(n)
    distances.fill(65535)
    for(let from=0;from<n;from++){
      const row=from*n;distances[row+from]=0;queue[0]=from;let length=1
      for(let cursor=0;cursor<length;cursor++){const current=queue[cursor];for(const id of neighbors[nodes[current]]){const next=local.get(id)!;if(distances[row+next]===65535){distances[row+next]=distances[row+current]+1;queue[length++]=next}}}
    }
    let first=0,second=0
    for(let i=0;i<n;i++)if(distances[i]>distances[first])first=i
    for(let i=0;i<n;i++)if(distances[first*n+i]>distances[first*n+second])second=i
    const diameter=Math.max(1,distances[first*n+second]),x=new Float64Array(n),y=new Float64Array(n)
    for(let i=0;i<n;i++){
      const a=distances[first*n+i],b=distances[second*n+i]
      x[i]=(a*a-b*b+diameter*diameter)/(2*diameter)
      y[i]=Math.sqrt(Math.max(0,a*a-x[i]*x[i]))*(i%2?1:-1)+Math.sin(nodes[i]*2.399963)*.02
    }
    const weights=new Float64Array(n),sumX=new Float64Array(n),sumY=new Float64Array(n)
    for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){const distance=distances[i*n+j],weight=1/(distance*distance);weights[i]+=weight;weights[j]+=weight}
    // Stress relaxation weights nearby source relations more strongly than distant pairs.
    // The explicit node cap keeps this small-overview operation off the100k path.
    for(let iteration=0;iteration<90;iteration++){
      sumX.fill(0);sumY.fill(0)
      for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
        const target=distances[i*n+j],weight=1/(target*target),dx=x[i]-x[j],dy=y[i]-y[j],length=Math.max(.01,Math.hypot(dx,dy)),tx=target*dx/length,ty=target*dy/length
        sumX[i]+=weight*(x[j]+tx);sumY[i]+=weight*(y[j]+ty);sumX[j]+=weight*(x[i]-tx);sumY[j]+=weight*(y[i]-ty)
      }
      for(let i=0;i<n;i++){x[i]=x[i]*.4+sumX[i]/weights[i]*.6;y[i]=y[i]*.4+sumY[i]/weights[i]*.6}
    }
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
    for(let i=0;i<n;i++){minX=Math.min(minX,x[i]);maxX=Math.max(maxX,x[i]);minY=Math.min(minY,y[i]);maxY=Math.max(maxY,y[i])}
    const padding=Math.min(24,rect.width*.12,rect.height*.12)
    for(let i=0;i<n;i++){
      positions[nodes[i]*2]=rect.x+padding+(x[i]-minX)/Math.max(.001,maxX-minX)*(rect.width-padding*2)
      positions[nodes[i]*2+1]=rect.y+padding+(y[i]-minY)/Math.max(.001,maxY-minY)*(rect.height-padding*2)
    }
  }
  function pack(groups:number[][],rect:Rect){
    if(groups.length===1){place(groups[0],rect);return}
    if(!groups.length)return
    const weights=groups.map(group=>group.length+2),total=weights.reduce((a,b)=>a+b,0)
    let split=1,weight=weights[0]
    while(split<groups.length-1&&weight<total/2)weight+=weights[split++]
    const ratio=weight/total,gap=8
    if(rect.width>=rect.height){const width=rect.width*ratio;pack(groups.slice(0,split),{...rect,width:Math.max(1,width-gap/2)});pack(groups.slice(split),{...rect,x:rect.x+width+gap/2,width:Math.max(1,rect.width-width-gap/2)})}
    else{const height=rect.height*ratio;pack(groups.slice(0,split),{...rect,height:Math.max(1,height-gap/2)});pack(groups.slice(split),{...rect,y:rect.y+height+gap/2,height:Math.max(1,rect.height-height-gap/2)})}
  }
  pack(components,{x:bounds.x+30,y:bounds.y+30,width:bounds.width-60,height:bounds.height-60})
  return positions
}
