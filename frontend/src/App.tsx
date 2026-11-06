import { useEffect, useRef, useState } from 'react'
import { Activity, ArrowDownToLine, ArrowRight, BarChart3, Check, ChevronRight, CircleHelp, Cpu, FlaskConical, Focus, ImagePlus, Layers3, LoaderCircle, Moon, RefreshCw, ScanLine, ShieldCheck, Sparkles, Sun, Upload, WandSparkles, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { artifactUrl, download, getModels, processImage } from './api'
import type { Metric, Mode, ModelResponse, Page, Result } from './types'
import ImageCompare from './components/ImageCompare'
import { Histogram, LatencyChart } from './components/Charts'
import BenchmarkViewer from './components/BenchmarkViewer'
import ResearchWorkspace from './components/ResearchWorkspace'
import RegionInspector from './components/RegionInspector'
import BenchmarkLibrary from './components/BenchmarkLibrary'

const pages: {id: Page; label: string; icon: LucideIcon; subtitle: string}[] = [
  {id:'studio', label:'Restoration studio', icon:WandSparkles, subtitle:'Bring the unseen into focus.'},
  {id:'analyzer', label:'Image analyzer', icon:ScanLine, subtitle:'Understand the light, noise, and detail in your image.'},
  {id:'pipeline', label:'Pipeline explorer', icon:Layers3, subtitle:'Follow every stage of the restoration.'},
  {id:'comparison', label:'Model comparison', icon:Layers3, subtitle:'Compare independent methods on the same image.'},
  {id:'analytics', label:'Performance analytics', icon:BarChart3, subtitle:'Measured performance. Transparent evaluation.'},
  {id:'quality', label:'Quality diagnostics', icon:ShieldCheck, subtitle:'Inspect detected limitations and controller decisions.'},
]
const modes: {id:Mode; label:string; caption:string; icon:LucideIcon}[] = [
  {id:'auto',label:'Auto',caption:'Choose from available methods',icon:Sparkles},
  {id:'classical',label:'Classical',caption:'Retinex Â· adaptive contrast',icon:Sun},
  {id:'deep',label:'Deep learning',caption:'Pretrained Retinexformer',icon:Cpu},
  {id:'hybrid',label:'Adaptive hybrid',caption:'Spatial confidence fusion',icon:Layers3},
]
const stageNames: Record<string,string> = {restored:'Restoration before finish',export_4k:'4K export (interpolated)',original:'Original input',illumination_original:'Maximum-RGB illumination',illumination_refined:'Refined illumination',reflectance:'Reflectance estimate',retinex:'Bounded Retinex',denoised:'Edge-preserving denoising',clahe:'Adaptive CLAHE',colour_corrected:'Colour correction',classical:'Classical output',deep:'Retinexformer output',fusion_map:'Selected neural contribution',fusion_raw:'Spatial weights before selection',artifact_risk:'Final artifact risk',halo_risk:'Edge-ring overshoot risk',detail_loss_map:'Local detail-loss risk',noise_amplification_map:'Residual noise risk',colour_shift_map:'Chromaticity-change risk',new_clipping_map:'New clipping risk',contrast_risk:'Local contrast risk',hybrid:'Controller output',enhanced:'Final enhanced image',noise_map:'High-pass residual',edge_map:'Edge map',contrast_map:'Local contrast map',reference:'Reference image'}
const metricNames: Record<string,string> = {psnr:'PSNR (dB) â†‘',ssim:'SSIM â†‘',lpips:'LPIPS â†“',niqe:'NIQE â†“',latency_ms:'Latency (ms) â†“',noise_suppression:'Noise estimate reduction â†‘',edge_preservation:'Gradient correlation â†‘',highlight_clipping:'Highlight clipping â†“',noise_estimate:'Noise estimate â†“'}

export function metricText(metric?: Metric) {
  if (metric?.infinite) return 'âˆž'
  if (!metric?.available || metric.value == null) return 'Unavailable'
  return metric.value.toLocaleString(undefined,{maximumFractionDigits: metric.value > 10 ? 1 : 4})
}

function MetricTable({result}: {result: Result}) {
  const entries = Object.entries(result.comparisons).filter(([,item])=>item.metrics)
  const groups = entries.length ? entries : [[result.executed_mode,{metrics:result.metrics}] as const]
  return <div className="table-scroll"><table><thead><tr><th>Measured indicator</th>{groups.map(([name])=><th key={name}>{name}</th>)}</tr></thead><tbody>{Object.keys(metricNames).map(name=><tr key={name}><td>{metricNames[name]}</td>{groups.map(([mode,item])=><td key={mode} title={item.metrics?.[name]?.reason}>{metricText(item.metrics?.[name])}</td>)}</tr>)}</tbody></table></div>
}

function Empty({title,children}: {title:string;children: React.ReactNode}) {
  return <div className="section-empty"><Focus size={32}/><h3>{title}</h3><p>{children}</p></div>
}

export default function App() {
  const [page,setPage] = useState<Page>('studio')
  const [modelState,setModelState] = useState<ModelResponse|null>(null)
  const [connection,setConnection] = useState<'connecting'|'online'|'offline'>('connecting')
  const [mode,setMode] = useState<Mode>('auto')
  const [file,setFile] = useState<File|null>(null)
  const [preview,setPreview] = useState('')
  const [reference,setReference] = useState<File|null>(null)
  const [result,setResult] = useState<Result|null>(null)
  const [history,setHistory] = useState<Result[]>([])
  const [strength,setStrength] = useState(1)
  const [vivid,setVivid] = useState(true)
  const [upscale4k,setUpscale4k] = useState(false)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const [dragging,setDragging] = useState(false)
  const [selectedStage,setSelectedStage] = useState('enhanced')
  const [help,setHelp] = useState(false)
  const helpOpener=useRef<HTMLElement|null>(null)
  function openHelp(){helpOpener.current=document.activeElement as HTMLElement;setHelp(true)}
  function handleHelpKey(e:React.KeyboardEvent<HTMLDivElement>){
    if(e.key==='Escape'){e.preventDefault();setHelp(false)}
    if(e.key==='Tab'){
      const nodes=e.currentTarget.querySelectorAll<HTMLButtonElement>('button:not([disabled])')
      const first=nodes[0],last=nodes[nodes.length-1]
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}
    }
  }
  useEffect(()=>{if(!help&&helpOpener.current){helpOpener.current.focus();helpOpener.current=null}},[help])
  const input = useRef<HTMLInputElement>(null)
  const abort = useRef<AbortController|null>(null)
  const requestId = useRef(0)

  async function refreshModels() {
    setConnection('connecting')
    try { setModelState(await getModels());setConnection('online') }
    catch { setConnection('offline') }
  }
  useEffect(()=>{void refreshModels();return()=>abort.current?.abort()},[])
  useEffect(()=>{if(!file){setPreview('');return}const url=URL.createObjectURL(file);setPreview(url);return()=>URL.revokeObjectURL(url)},[file])

  function chooseFile(candidate?: File) {
    if(!candidate)return
    if(!/\.(jpe?g|png|webp)$/i.test(candidate.name)) {setError('Choose a JPEG, PNG, or WebP image.');return}
    if(candidate.size > (modelState?.limits.upload_mb??20)*1024**2) {setError(`Choose an image smaller than ${modelState?.limits.upload_mb??20} MB.`);return}
    requestId.current++;abort.current?.abort();setBusy(false);setFile(candidate);setResult(null);setError('');setSelectedStage('enhanced');setReference(null)
    if(input.current)input.current.value=''
  }
  function reset() { requestId.current++;abort.current?.abort();setFile(null);setResult(null);setReference(null);setBusy(false);setError('') }
  async function run(endpoint:'enhance'|'analyze'|'compare'|'evaluate'='enhance') {
    if(!file)return
    const current = ++requestId.current
    abort.current?.abort();const controller=new AbortController();abort.current=controller
    setBusy(true);setError('')
    try {
      const next=await processImage(file,endpoint,mode,strength,reference,controller.signal,{vivid,upscale4k})
      if(current!==requestId.current)return
      setResult(next);setSelectedStage(next.artifacts.enhanced?'enhanced':'original')
      setHistory(items=>[next,...items].slice(0,20))
    } catch(err) {if(current===requestId.current && !(err instanceof DOMException&&err.name==='AbortError'))setError(err instanceof Error?err.message:'Processing failed.')}
    finally {if(current===requestId.current)setBusy(false)}
  }
  async function save(url:string,name:string) {try{await download(url,name)}catch(err){setError((err as Error).message)}}
  const currentPage = pages.find(item=>item.id===page)!
  const enhanced = result?.artifacts.enhanced
  const activeModel = modelState?.models[mode]
  const canRun = !!file && !busy && connection==='online' && (activeModel?.available??false)
  const unavailableReason = modelState?.models.deep.reason

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#studio" className="brand" onClick={e=>{e.preventDefault();setPage('studio')}} aria-label="LumaRestore home"><div className="brand-symbol"><Sun size={24}/></div><div>Luma<span>Restore</span><small>AI IMAGING WORKSPACE</small></div></a>
      <div className="workspace-label">WORKSPACE <span>01</span></div>
      <nav aria-label="Workspace pages">{pages.map(item=><button key={item.id} aria-label={item.label} title={item.label} aria-current={page===item.id?'page':undefined} className={page===item.id?'active':''} onClick={()=>setPage(item.id)}><item.icon size={18}/><span>{item.label}</span>{page===item.id&&<span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-card"><span className="small-icon"><ShieldCheck size={17}/></span><strong>Local image processing</strong><p>Your images are processed by your own backend.</p></div><button className="help-button" onClick={openHelp}><CircleHelp size={16}/> Setup & evaluation notes <ChevronRight size={14}/></button><div className="version"><span className="tiny-dot"/> LumaRestore AI <span>v1.0</span></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={13}/><span>{currentPage.label}</span></div><div className="top-status"><span className={`connection ${connection}`}><i/>{connection==='online'?'Backend connected':connection==='connecting'?'Connecting':'Backend offline'}</span><button className="icon-button" aria-label="Refresh backend status" onClick={()=>void refreshModels()}><RefreshCw size={15}/></button><span className="avatar">LR</span></div></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow"><span/> LOW-LIGHT INTELLIGENCE</div><h1>{currentPage.label}</h1><p>{currentPage.subtitle}</p></div><div className="heading-badge"><Cpu size={15}/>{modelState?.models.deep.available?`Retinexformer Â· ${modelState.models.deep.device}`:'Classical engine ready'}</div></div>
        {connection==='offline'&&<div className="notice warning" role="status">Start the FastAPI backend on port 8000, then refresh the connection. <button onClick={()=>void refreshModels()}>Retry connection</button></div>}
        {error&&<div className="notice error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
        <input ref={input} type="file" accept=".jpg,.jpeg,.png,.webp" className="sr-only" aria-label="Upload image" onChange={e=>chooseFile(e.target.files?.[0])}/>
        {page==='studio'&&<>
          <div className="studio-layout">
            <section className="panel studio-panel" aria-label="Image restoration workspace"><div className="panel-heading"><div><span className="step-number">01</span><h2>Image workspace</h2>{file&&<span className="file-tag">{file.name}</span>}</div><span className="subtle">{result?`${result.image.processed_size.join(' Ã— ')} px`:'JPG, PNG, WebP'}</span></div>
              {!file?<div className={`upload-zone ${dragging?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);chooseFile(e.dataTransfer.files[0])}}>
                <div className="upload-art"><span className="orbit orbit-one"/><span className="orbit orbit-two"/><div className="upload-art-icon"><ImagePlus size={32} strokeWidth={1.35}/></div><span className="art-spark s1"/><span className="art-spark s2"/><span className="art-spark s3"/></div>
                <div className="upload-eyebrow">A LITTLE LIGHT GOES A LONG WAY</div><h3>Reveal what the darkness hides.</h3><p>Drop a low-light image here to begin restoration.</p><button className="primary-button" onClick={()=>input.current?.click()}><Upload size={16}/> Browse images</button><span className="upload-details">JPEG, PNG or WebP Â· up to {modelState?.limits.upload_mb??20} MB</span>
                <div className="upload-footnote"><ShieldCheck size={13}/> Real processing. No paid AI API.</div>
              </div>:<><ImageCompare original={result?artifactUrl(result.artifacts.original):preview} enhanced={enhanced?artifactUrl(enhanced):undefined} label={result?.executed_mode==='deep'?'Retinexformer':'Restored'}/><div className="image-actions">{result?.artifacts.export_4k&&<button className="download-button" onClick={()=>void save(result.artifacts.export_4k,'lumarestore-4k.png')}><ArrowDownToLine size={16}/> Download 4K</button>}<button className="text-button" disabled={busy} onClick={()=>input.current?.click()}><ImagePlus size={15}/> Replace image</button><button className="text-button" onClick={reset}><RefreshCw size={14}/> Reset</button>{enhanced&&<button className="download-button" onClick={()=>void save(enhanced,`lumarestore-${result!.executed_mode}.png`)}><ArrowDownToLine size={16}/> Download PNG</button>}</div></>}
              {busy&&<div className="processing-overlay" role="status"><LoaderCircle className="spin" size={28}/><strong>Restoring your image</strong><span>Analysis â†’ restoration â†’ quality assessment</span></div>}
            </section>
            <aside className="controls-stack"><section className="panel settings-panel"><div className="panel-heading"><div><span className="step-number">02</span><h2>Restoration engine</h2></div></div><div className="mode-options">{modes.map(item=>{const available=modelState?.models[item.id]?.available??(item.id==='auto'||item.id==='classical');return <button key={item.id} className={`mode-option ${mode===item.id?'selected':''}`} aria-pressed={mode===item.id} disabled={busy||!available} title={!available?modelState?.models[item.id]?.reason:undefined} onClick={()=>setMode(item.id)}><span className="mode-icon"><item.icon size={17}/></span><span><strong>{item.label}{item.id==='auto'&&<em>RECOMMENDED</em>}</strong><small>{available?item.caption:'Setup required'}</small></span><span className="radio-mark">{mode===item.id&&<Check size={11}/>}</span></button>})}</div>
              <div className="strength-control"><label htmlFor="strength">Classical strength <span>{strength.toFixed(2)}Ã—</span></label><input id="strength" type="range" min="0.3" max="1.5" step="0.05" value={strength} disabled={busy||mode==='deep'} onChange={e=>setStrength(Number(e.target.value))}/><div><span>Gentle</span><span>Stronger</span></div></div>
              <div className="finish-controls"><label><input type="checkbox" checked={vivid} disabled={busy} onChange={e=>setVivid(e.target.checked)}/> Vivid finish</label><p>Brighter midtones, richer colours and subtle sharpening.</p><label><input type="checkbox" checked={upscale4k} disabled={busy} onChange={e=>setUpscale4k(e.target.checked)}/> Create 4K export</label><p>3840px long edge, original aspect ratio. Enlarging does not recover missing detail.</p></div>
              <button className="primary-button enhance-button" disabled={!canRun} onClick={()=>void run()}>{busy?<LoaderCircle size={17} className="spin"/>:<WandSparkles size={17}/>} {busy?'Processingâ€¦':'Enhance image'}{!busy&&<ArrowRight size={16}/>}</button><p className="control-note">Parameters adapt to illumination, noise, and colour balance.</p>
            </section><section className="panel engine-note"><div><Activity size={17}/><h3>Engine status</h3></div><p><span className="status-dot"/>Classical CV <strong>Available</strong></p><p><span className={`status-dot ${modelState?.models.deep.available?'':'muted'}`}/>Retinexformer <strong>{modelState?.models.deep.available?'Available':'Not configured'}</strong></p>{!modelState?.models.deep.available&&<small>{unavailableReason||'Checking pretrained model availabilityâ€¦'}</small>}<button className="text-button" onClick={openHelp}>View setup notes <ArrowRight size={13}/></button></section></aside>
          </div>
          <div className="stat-row">{[{icon:Sun,label:'Mean brightness',value:result?`${(result.analysis.mean_brightness*100).toFixed(1)}%`:'â€”',caption:result?.analysis.classification??'Awaiting an image'},{icon:Moon,label:'Dark pixels',value:result?`${result.analysis.dark_pixel_percentage.toFixed(1)}%`:'â€”',caption:'Luminance below 0.15'},{icon:ScanLine,label:'Noise estimate',value:result?result.analysis.noise_estimate.toFixed(4):'â€”',caption:'Flat-region Haar MAD'},{icon:Activity,label:'Processing time',value:result?`${Math.round(result.latency_ms)} ms`:'â€”',caption:result?`Executed: ${result.executed_mode}`:'Measured on your hardware'}].map(item=><div className="stat-card" key={item.label}><div><item.icon size={15}/><span>{item.label}</span></div><strong>{item.value}</strong><small>{item.caption}</small></div>)}</div>
          {result&&enhanced&&<div className="result-strip"><ShieldCheck size={18}/><div><strong>{result.diagnostics.length?`${result.diagnostics.length} quality observation${result.diagnostics.length===1?'':'s'}`:'No configured quality warning was triggered'}</strong><p>{result.controller?.explanation??(result.executed_mode==='deep'?'Official Retinexformer ran independently; no fusion controller was used.':'Illumination, denoising, and contrast were adapted to this image.')}</p></div><button className="text-button" onClick={()=>setPage('quality')}>Inspect result <ArrowRight size={14}/></button></div>}
        </>}
        {page!=='studio'&&<div className="context-bar"><div><ImagePlus size={17}/><span>{file?.name??'No image selected'}</span></div><button className="text-button" disabled={busy} onClick={()=>input.current?.click()}>{file?'Change image':'Upload image'} <Upload size={14}/></button>{file&&<button className="primary-button compact" disabled={!canRun} onClick={()=>void run(page==='analyzer'?'analyze':page==='comparison'||page==='analytics'?'compare':'enhance')}>{busy?<LoaderCircle className="spin" size={15}/>:<WandSparkles size={15}/>} {busy?'Processingâ€¦':page==='analyzer'?'Analyze image':page==='comparison'||page==='analytics'?'Run comparison':'Restore image'}</button>}</div>}
        {page==='analyzer'&&(result?<><div className="section-grid"><section className="panel padded"><div className="section-title"><h2>Luminance distribution</h2><span className="tag">{result.analysis.classification}</span></div><Histogram analysis={result.analysis}/><p className="caption">Measured Rec.709 display luma, 64 bins; analysis is sampled to 768 px.</p></section><section className="panel padded"><h2>Image characteristics</h2><dl className="characteristics">{[['Mean brightness',(result.analysis.mean_brightness*100).toFixed(2)+'%'],['Median luminance',result.analysis.median_luminance.toFixed(4)],['Local contrast',result.analysis.local_contrast.toFixed(4)],['Edge density',(result.analysis.edge_density*100).toFixed(2)+'%'],['Saturation',result.analysis.saturation.toFixed(4)],['Channel imbalance',result.analysis.colour_imbalance.toFixed(4)],['Dynamic range',result.analysis.dynamic_range.toFixed(4)],['Uneven illumination',result.analysis.nonuniform_illumination.toFixed(4)],['Shadow clipping',(result.analysis.shadow_clipping*100).toFixed(2)+'%'],['Highlight clipping',(result.analysis.highlight_clipping*100).toFixed(2)+'%']].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section></div><div className="artifact-grid">{['illumination_refined','edge_map','noise_map','contrast_map'].map(name=><figure className="panel artifact-card" key={name}><img src={artifactUrl(result.artifacts[name])} alt={stageNames[name]}/><figcaption>{stageNames[name]}</figcaption></figure>)}</div><p className="caption">{result.analysis.noise_protocol} Residual maps can contain both texture and noise.</p></>:<Empty title="Read the image before restoring it">Upload an image and run analysis to see its actual illumination, noise, and structure.</Empty>)}
        {page==='pipeline'&&(result?<div className="pipeline-layout"><section className="panel stages-list"><h2>Processing stages</h2>{Object.keys(stageNames).filter(name=>result.artifacts[name]).map((name,i)=><button className={name===selectedStage?'selected':''} key={name} onClick={()=>setSelectedStage(name)}><span>{String(i+1).padStart(2,'0')}</span>{stageNames[name]}<ChevronRight size={14}/></button>)}</section><section className="panel padded"><div className="section-title"><h2>{stageNames[selectedStage]}</h2><button className="text-button" onClick={()=>void save(result.artifacts[selectedStage],`${selectedStage}.png`)}><ArrowDownToLine size={15}/> Download</button></div><img className="stage-preview" src={artifactUrl(result.artifacts[selectedStage])} alt={stageNames[selectedStage]}/><details className="parameters"><summary>Executed parameters</summary><pre>{JSON.stringify(result.parameters,null,2)}</pre></details></section></div>:<Empty title="Every stage, visible">Analyze or restore an image to inspect the actual maps and intermediate outputs.</Empty>)}
        {page==='comparison'&&<><div className="reference-row"><div><h2>Aligned reference <span className="optional">optional</span></h2><p>Enable PSNR, SSIM, and optional LPIPS. Match input dimensions and alignment.</p></div><label className="secondary-button reference-picker"><ImagePlus size={15}/>{reference?reference.name:'Choose reference'}<input type="file" accept=".jpg,.jpeg,.png,.webp" disabled={busy} onChange={e=>setReference(e.target.files?.[0]??null)}/></label>{reference&&<button className="icon-button" aria-label="Remove reference" onClick={()=>setReference(null)}><X size={15}/></button>}</div>{result&&Object.keys(result.comparisons).length?<><div className="candidate-grid">{(['classical','deep','hybrid'] as const).map(name=><section className="panel candidate" key={name}><h2>{name==='deep'?'Retinexformer':name==='hybrid'?'Adaptive hybrid':'Classical CV'}</h2>{result.artifacts[name]?<><img src={artifactUrl(result.artifacts[name])} alt={`${name} output`}/><p>{metricText(result.comparisons[name]?.metrics?.latency_ms)} ms</p><button className="text-button" onClick={()=>void save(result.artifacts[name],`${name}.png`)}><ArrowDownToLine size={14}/>Download output</button></>:<div className="candidate-unavailable"><Cpu size={25}/><strong>Model unavailable</strong><p>{result.comparisons[name]?.reason}</p></div>}</section>)}</div><section className="panel padded"><h2>Same-image evaluation</h2><MetricTable result={result}/></section></>:<Empty title="One input. Independent approaches.">Choose an image and run comparison to generate real candidates and measured indicators.</Empty>}</>}
        {page==='analytics'&&<BenchmarkLibrary/>}
        {page==='analytics'&&<ResearchWorkspace file={file}/>}
        {page==='analytics'&&<BenchmarkViewer/>}
        {page==='analytics'&&(result&&Object.keys(result.metrics).length?<><div className="section-grid"><section className="panel padded"><h2>Pipeline latency</h2>{Object.keys(result.comparisons).length?<LatencyChart comparisons={result.comparisons}/>:<div className="latency-readout"><strong>{Math.round(result.latency_ms)}<small>ms</small></strong><p>Analyze + restore + diagnostics. Run comparison for per-method timing.</p></div>}<p className="caption">Wall-clock measurements on this hardware. Hybrid includes candidate generation. These are not dataset benchmarks.</p></section><section className="panel padded"><h2>Evaluation exports</h2><p className="body-copy">Export the computed measurements and configuration for this image. Unsupported metrics include a reason.</p><div className="export-buttons"><button className="secondary-button" onClick={()=>void save(`/api/results/${result.id}/metrics`,'lumarestore-metrics.csv')}><ArrowDownToLine size={15}/> Metrics CSV</button><button className="secondary-button" onClick={()=>void save(`/api/results/${result.id}/report`,'lumarestore-report.json')}><ArrowDownToLine size={15}/> Full JSON report</button></div><p className="caption">Batch benchmarks and nine ablation variants can be run with the included evaluation CLI. No benchmark data has been preloaded.</p></section></div><section className="panel padded"><h2>Measured indicators</h2><MetricTable result={result}/><p className="caption">Noise reduction and gradient correlation are input-relative diagnostics. Exposure changes affect both. NIQE alone does not determine the selected output.</p></section><section className="panel padded history"><h2>Session results</h2>{history.map(item=><button key={item.id} onClick={()=>{setResult(item);setSelectedStage(item.artifacts.enhanced?'enhanced':'original')}}><span>{new Date(item.created_at).toLocaleTimeString()}</span><strong>{item.kind} Â· {item.executed_mode}</strong><span>{Math.round(item.latency_ms)} ms</span><ChevronRight size={14}/></button>)}</section></>:<Empty title="Measurements begin with your image">Run restoration or a model comparison. Metrics and exports will appear here after processing.</Empty>)}
        {page==='quality'&&(result?<><div className="section-grid"><section className="panel padded"><div className="section-title"><h2>Controller decision</h2><span className="tag">{result.executed_mode}</span></div><p className="body-copy">{result.controller?.explanation??(result.kind==='analyze'?'Analysis only. No restoration has been executed.':result.executed_mode==='deep'?'Official Retinexformer ran independently. No fusion controller was used.':'The classical pipeline adapted its parameters to the measured input. Neural fusion was not used.')}</p>{result.controller&&<><p className="caption">Candidate mix before highlight and artifact safeguards</p><div className="contribution-bar"><span style={{width:`${result.controller.deep_contribution*100}%`}}/></div><div className="contribution-labels"><span>Neural {(result.controller.deep_contribution*100).toFixed(1)}%</span><span>Classical {(result.controller.classical_contribution*100).toFixed(1)}%</span></div></>}<details className="parameters"><summary>Selected parameters</summary><pre>{JSON.stringify(result.parameters,null,2)}</pre></details></section><section className="panel padded"><h2>Processing notes</h2><ul className="notes-list">{result.notices.map((notice,i)=><li key={i}>{notice}</li>)}{result.controller?.warnings.map((notice,i)=><li key={i+1000}>{notice}</li>)}<li>Detectors are transparent heuristics. An absence of warnings does not prove artifact-free restoration.</li><li>Inspect texture and bright sources at full size before drawing quality conclusions.</li></ul></section></div><section className="panel padded"><h2>Detected observations <span className="count-badge">{result.diagnostics.length}</span></h2>{result.diagnostics.length?result.diagnostics.map(item=><article className="diagnostic" key={item.code}><span className="diagnostic-icon"><Activity size={18}/></span><div><h3>{item.problem}</h3><span className="caption">Stage: {item.stage}</span><p>{item.action}</p><p className="caption">{item.limitation}</p></div></article>):<p className="body-copy">{result.kind==='analyze'?'Run restoration to generate output quality diagnostics.':'No configured warning threshold was triggered for this result.'}</p>}</section>{enhanced&&<RegionInspector result={result}/>}</>:<Empty title="Understand the result and its limits">Run restoration to see detected quality warnings, applied safeguards, and controller decisions.</Empty>)}
        <footer><span>LumaRestore AI <span className="footer-divider">/</span> Adaptive low-light restoration</span><span><FlaskConical size={12}/> Research workspace Â· P1</span></footer>
      </main>
    </div>
    {help&&<div className="modal-backdrop" onKeyDown={handleHelpKey} onClick={()=>setHelp(false)}><section className="modal panel" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={e=>e.stopPropagation()}><div className="section-title"><h2 id="help-title">Setup & evaluation notes</h2><button className="icon-button" aria-label="Close setup notes" autoFocus onClick={()=>setHelp(false)}><X size={18}/></button></div><p>Classical enhancement works without model weights or a dataset. Retinexformer uses the official architecture with a compatible pretrained checkpoint.</p><ol><li>Install <code>backend/requirements-deep.txt</code> in the project virtual environment.</li><li>Use <code>scripts/setup_model.py</code> to install the official LOL-v1 weights.</li><li>Restart the backend and refresh model status.</li></ol><p>Read the README for commands and verified upstream sources. Deep and hybrid modes stay unavailable if weights cannot be validated. Synthetic tests verify correctness; dataset benchmarks are needed for restoration-quality claims.</p><p>Optional LPIPS and NIQE require <code>requirements-iqa.txt</code>, metric weights, and <code>LUMA_ENABLE_IQA=true</code>.</p><button className="primary-button" onClick={()=>setHelp(false)}>Back to workspace</button></section></div>}
  </div>
}
