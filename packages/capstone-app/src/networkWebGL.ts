import type {SceneCamera} from './networkScene'
import type {SceneFrame} from './networkScene.worker'
import {NETWORK_GLYPH_FRAGMENT} from './networkSymbols'

/** Bounded visible buffers; camera motion changes uniforms, not the full graph. */
export function createNetworkRenderer(canvas:HTMLCanvasElement){
  const gl=canvas.getContext('webgl',{antialias:true,alpha:false,preserveDrawingBuffer:false})
  if(!gl)throw new Error('当前浏览器未提供 WebGL，请使用支持 WebGL 的浏览器查看大图。')
  function shader(type:number,source:string){const s=gl!.createShader(type)!;gl!.shaderSource(s,source);gl!.compileShader(s);if(!gl!.getShaderParameter(s,gl!.COMPILE_STATUS))throw new Error(gl!.getShaderInfoLog(s)||'Shader compile failed');return s}
  function program(point:boolean){
    const p=gl!.createProgram()!,v=shader(gl!.VERTEX_SHADER,`attribute vec2 position;attribute vec4 color;${point?'attribute float size;attribute float kind;varying float symbol;':''}uniform vec4 camera;uniform vec2 viewport;uniform float ratio;varying vec4 tint;void main(){vec2 xy=(position-camera.xy)/camera.zw;gl_Position=vec4(xy.x*2.0-1.0,1.0-xy.y*2.0,0.0,1.0);tint=color;${point?'gl_PointSize=size*ratio;symbol=kind;':''}}`),
      f=shader(gl!.FRAGMENT_SHADER,`precision mediump float;varying vec4 tint;${point?'varying float symbol;':''}void main(){${point?`vec2 p=gl_PointCoord*2.0-1.0;float d=length(p);${NETWORK_GLYPH_FRAGMENT}`:''}gl_FragColor=tint;}`)
    gl!.attachShader(p,v);gl!.attachShader(p,f);gl!.linkProgram(p);gl!.deleteShader(v);gl!.deleteShader(f)
    if(!gl!.getProgramParameter(p,gl!.LINK_STATUS))throw new Error('Network shader link failed')
    return {program:p,buffer:gl!.createBuffer()!,point}
  }
  const line=program(false),point=program(true)
  let lineCount=0,pointCount=0,disposed=false
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA)
  function draw(camera:SceneCamera){
    if(disposed)return
    const ratio=Math.min(2,window.devicePixelRatio||1),width=Math.max(1,canvas.clientWidth),height=Math.max(1,canvas.clientHeight)
    if(canvas.width!==Math.round(width*ratio)||canvas.height!==Math.round(height*ratio)){canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio)}
    gl!.viewport(0,0,canvas.width,canvas.height);gl!.clearColor(1,1,1,1);gl!.clear(gl!.COLOR_BUFFER_BIT)
    for(const state of [line,point]){
      const p=state.program,stride=state.point?32:24
      gl!.useProgram(p);gl!.bindBuffer(gl!.ARRAY_BUFFER,state.buffer)
      const attribute=(name:string,size:number,offset:number)=>{const at=gl!.getAttribLocation(p,name);if(at>=0){gl!.enableVertexAttribArray(at);gl!.vertexAttribPointer(at,size,gl!.FLOAT,false,stride,offset)}}
      attribute('position',2,0);attribute('color',4,state.point?16:8)
      if(state.point){attribute('size',1,8);attribute('kind',1,12)}
      gl!.uniform4f(gl!.getUniformLocation(p,'camera'),camera.x,camera.y,camera.width,camera.height);gl!.uniform1f(gl!.getUniformLocation(p,'ratio'),ratio)
      gl!.drawArrays(state.point?gl!.POINTS:gl!.LINES,0,state.point?pointCount:lineCount)
    }
  }
  return {draw,upload(frame:SceneFrame){for(const [state,data] of [[line,frame.lines],[point,frame.points]] as const){gl!.bindBuffer(gl!.ARRAY_BUFFER,state.buffer);gl!.bufferData(gl!.ARRAY_BUFFER,data,gl!.DYNAMIC_DRAW)}lineCount=frame.lines.length/6;pointCount=frame.points.length/8},dispose(){disposed=true;for(const state of [line,point]){gl!.deleteBuffer(state.buffer);gl!.deleteProgram(state.program)}}}
}
