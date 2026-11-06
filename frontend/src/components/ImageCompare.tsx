import { useEffect, useRef, useState } from 'react'
import { Columns2, SlidersHorizontal, ZoomIn, ZoomOut, RotateCcw, GripVertical } from 'lucide-react'
import type { Region } from '../types'

interface Props { original: string; enhanced?: string; label?: string; region?:Region }

export default function ImageCompare({original, enhanced, label = 'Enhanced',region}: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const loaded = useRef<{before: HTMLImageElement; after?: HTMLImageElement} | null>(null)
  const drag = useRef<{x:number;y:number;px:number;py:number} | null>(null)
  const [split, setSplit] = useState(50)
  const [side, setSide] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({x:0, y:0})
  const [revision, setRevision] = useState(0)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    let active = true
    const load = (url: string) => new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image(); img.onload = () => resolve(img); img.onerror = reject; img.src = url
    })
    setLoadError(false); loaded.current = null; setZoom(1); setPan({x:0,y:0})
    Promise.all([load(original), enhanced ? load(enhanced) : Promise.resolve(undefined)]).then(([before, after]) => {
      if (active) { loaded.current = {before, after}; setRevision(x => x+1) }
    }).catch(() => { if(active) setLoadError(true) })
    return () => { active = false }
  }, [original, enhanced])

  useEffect(() => {
    const draw = () => {
      const el = canvas.current, container = frame.current, images = loaded.current
      if (!el || !container || !images) return
      const width = container.clientWidth, height = container.clientHeight
      const dpr = window.devicePixelRatio || 1
      el.width = width*dpr; el.height = height*dpr
      const ctx = el.getContext('2d')!
      ctx.scale(dpr,dpr); ctx.clearRect(0,0,width,height)
      const paint = (image: HTMLImageElement, left: number, areaWidth: number) => {
        const sx=(region?.x??0)*image.width,sy=(region?.y??0)*image.height
        const sw=Math.max(1,(region?.width??1)*image.width),sh=Math.max(1,(region?.height??1)*image.height)
        const scale = Math.min(areaWidth/sw, height/sh) * zoom
        const w = sw * scale, h = sh * scale
        ctx.drawImage(image,sx,sy,sw,sh,left + (areaWidth-w)/2 + pan.x, (height-h)/2 + pan.y, w, h)
      }
      if (side && images.after) {
        ctx.save(); ctx.beginPath(); ctx.rect(0,0,width/2,height); ctx.clip(); paint(images.before,0,width/2); ctx.restore()
        ctx.save(); ctx.beginPath(); ctx.rect(width/2,0,width/2,height); ctx.clip(); paint(images.after,width/2,width/2); ctx.restore()
        ctx.fillStyle = '#627b8a'; ctx.fillRect(width/2-1,0,2,height)
      } else {
        paint(images.after || images.before,0,width)
        if(images.after) { ctx.save(); ctx.beginPath(); ctx.rect(0,0,width*split/100,height); ctx.clip(); paint(images.before,0,width); ctx.restore() }
      }
    }
    draw()
    const observer = new ResizeObserver(draw)
    if(frame.current) observer.observe(frame.current)
    return () => observer.disconnect()
  }, [split,side,zoom,pan,revision,region])

  return <div className="comparison-shell">
    <div className="image-toolbar"><div className="segmented">
      <button aria-pressed={!side} onClick={() => setSide(false)}><SlidersHorizontal size={14}/> Slider</button>
      <button aria-pressed={side} onClick={() => setSide(true)} disabled={!enhanced}><Columns2 size={14}/> Side by side</button>
    </div><div className="zoom-controls">
      <button aria-label="Zoom out" disabled={zoom<=1} onClick={() => setZoom(x=>Math.max(1,x-.25))}><ZoomOut size={16}/></button>
      <span>{Math.round(zoom*100)}%</span><button aria-label="Zoom in" disabled={zoom>=4} onClick={() => setZoom(x=>Math.min(4,x+.25))}><ZoomIn size={16}/></button>
      <button aria-label="Reset view" onClick={()=>{setZoom(1);setPan({x:0,y:0})}}><RotateCcw size={14}/></button>
    </div></div>
    <div className={`image-frame ${zoom>1?'pannable':''}`} ref={frame}
      onPointerDown={e=>{if(zoom>1){e.currentTarget.setPointerCapture(e.pointerId);drag.current={x:e.clientX,y:e.clientY,px:pan.x,py:pan.y}}}}
      onPointerMove={e=>{if(drag.current)setPan({x:drag.current.px+e.clientX-drag.current.x,y:drag.current.py+e.clientY-drag.current.y})}}
      onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}}>
      <canvas ref={canvas} aria-label={enhanced?'Original and restored image comparison':'Original uploaded image'} role="img"/>
      <span className="image-label before">Original</span>{enhanced&&<span className="image-label after">{label}</span>}
      {enhanced&&!side&&<div className="split-marker" style={{left:`${split}%`}}><span><GripVertical size={16}/></span></div>}
      {loadError&&<div className="canvas-error">Image could not be loaded. Run restoration again.</div>}
    </div>
    {enhanced&&!side&&<div className="slider-control"><span>Original</span><input aria-label="Before and after comparison" type="range" min="0" max="100" value={split} onChange={e=>setSplit(Number(e.target.value))}/><span>Restored</span></div>}
    <div className="viewer-hint">{zoom>1?'Drag the image to pan.':'Zoom to inspect details.'} {enhanced?'Use the slider to compare the same region.':''}</div>
  </div>
}
