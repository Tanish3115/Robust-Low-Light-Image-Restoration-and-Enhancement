import { useEffect, useMemo, useState } from 'react'
import { ArrowDownToLine, FlaskConical, LoaderCircle, Upload, X } from 'lucide-react'
import { artifactUrl,cancelJob,download,getJob,getJobs,runAblations,startBatch } from '../api'
import type { EvaluationJob,Result } from '../types'
import BenchmarkViewer from './BenchmarkViewer'

export default function ResearchWorkspace({file}:{file:File|null}) {
  const [reference,setReference]=useState<File|null>(null)
  const [ablation,setAblation]=useState<Result|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [files,setFiles]=useState<File[]>([])
  const [references,setReferences]=useState<File[]>([])
  const [allVariants,setAllVariants]=useState(false)
  const [job,setJob]=useState<EvaluationJob|null>(null)
  const [history,setHistory]=useState<EvaluationJob[]>([])
  const [sample,setSample]=useState('')
  useEffect(()=>{setAblation(null);setReference(null)},[file])
  useEffect(()=>{void getJobs().then(setHistory).catch(()=>{})},[])
  useEffect(()=>{
    if(!job || !['queued','running','cancelling'].includes(job.status))return
    let active=true;let timer:ReturnType<typeof setTimeout>;const controller=new AbortController()
    const poll=async()=>{try{const next=await getJob(job.id,controller.signal);if(active)setJob(next)}catch(err){if(active)setError((err as Error).message)}finally{if(active)timer=setTimeout(()=>void poll(),1200)}}
    timer=setTimeout(()=>void poll(),500)
    return()=>{active=false;clearTimeout(timer);controller.abort()}
  },[job?.id,job?.status])
  const ablationReport=useMemo(()=>{
    if(!ablation)return undefined
    const averages:Record<string,object>={};const unavailable:Record<string,string>={};const per_image=[]
    for(const [mode,item] of Object.entries(ablation.comparisons)) {
      if(!item.metrics){unavailable[mode]=item.reason??'Unavailable';continue}
      averages[mode]=Object.fromEntries(Object.entries(item.metrics).map(([name,metric])=>[name,{mean:metric.value,count:metric.value===null?0:1,infinite_count:metric.infinite?1:0}]))
      per_image.push({key:file?.name??'Uploaded image',mode})
    }
    return {partition:'uploaded image',ablations:true,protocol:'One-image measured ablation. Reference metrics require the aligned reference you supplied.',averages,per_image,unavailable}
  },[ablation,file])
  async function ablate() {
    if(!file)return;setBusy(true);setError('')
    try{setAblation(await runAblations(file,reference,new AbortController().signal))}catch(err){setError((err as Error).message)}finally{setBusy(false)}
  }
  async function start() {
    setError('');setBusy(true)
    try{setJob(await startBatch(files,references,allVariants));setHistory(await getJobs());setSample('')}catch(err){setError((err as Error).message)}finally{setBusy(false)}
  }
  async function save(url:string,name:string) {try{await download(url,name)}catch(err){setError((err as Error).message)}}
  const active=!!job&&['queued','running','cancelling'].includes(job.status)
  const report=job?.report as {per_image?:{key:string;mode:string;artifact?:string;original?:string}[]}|undefined
  const keys=[...new Set(report?.per_image?.map(row=>row.key)??[])]
  const chosen=sample||keys[0]
  return <>
    <section className="panel padded research-panel"><div className="section-title"><h2><FlaskConical size={16}/> Run ablation experiments</h2><span className="tag">9 real variants</span></div>
      <p className="body-copy">Use the selected image to measure Retinex stages, neural restoration, fixed/global/spatial fusion, and quality safeguards.</p>
      <div className="research-actions"><label className="secondary-button reference-picker"><Upload size={14}/>{reference?reference.name:'Aligned reference (optional)'}<input aria-label="Ablation reference" type="file" accept=".png,.jpg,.jpeg,.webp" disabled={busy} onChange={e=>setReference(e.target.files?.[0]??null)}/></label>{reference&&<button className="icon-button" aria-label="Remove ablation reference" onClick={()=>setReference(null)}><X size={15}/></button>}
      <button className="primary-button" disabled={!file||busy||active} onClick={()=>void ablate()}>{busy?<LoaderCircle className="spin" size={15}/>:<FlaskConical size={15}/>} Run all ablations</button></div>
      {!file&&<p className="caption">Select an image above to run its ablation study.</p>}
      {ablation&&<><div className="research-actions"><button className="secondary-button" onClick={()=>void save(`/api/results/${ablation.id}/metrics`,'ablation-metrics.csv')}><ArrowDownToLine size={14}/> CSV</button><button className="secondary-button" onClick={()=>void save(`/api/results/${ablation.id}/report`,'ablation-report.json')}>JSON report</button></div><div className="artifact-grid research-candidates">{Object.entries(ablation.comparisons).filter(([,item])=>item.metrics).map(([mode])=><figure className="panel artifact-card" key={mode}><img loading="lazy" src={artifactUrl(ablation.artifacts[mode])} alt={`${mode} ablation output`}/><figcaption>{mode.replaceAll('_',' ')}<button className="text-button" onClick={()=>void save(ablation.artifacts[mode],`${mode}.png`)}><ArrowDownToLine size={13}/> Save</button></figcaption></figure>)}</div></>}
    </section>
    {ablationReport&&<BenchmarkViewer reportData={ablationReport}/>}
    <section className="panel padded research-panel"><div className="section-title"><h2>Batch evaluation</h2><span className="tag">Background processing</span></div><p className="body-copy">Upload up to 32 images. Optional reference files must match the input filename stems and pixel alignment. Uploaded batches are labelled separately from official dataset partitions.</p>
      <div className="research-actions"><label className="secondary-button reference-picker"><Upload size={14}/> {files.length?`${files.length} input images`:'Choose input images'}<input aria-label="Batch input images" type="file" multiple accept=".png,.jpg,.jpeg,.webp" disabled={busy||active} onChange={e=>setFiles(Array.from(e.target.files??[]))}/></label><label className="secondary-button reference-picker"><Upload size={14}/>{references.length?`${references.length} references`:'Choose references (optional)'}<input aria-label="Batch reference images" type="file" multiple accept=".png,.jpg,.jpeg,.webp" disabled={busy||active} onChange={e=>setReferences(Array.from(e.target.files??[]))}/></label></div>
      <label className="research-checkbox"><input type="checkbox" checked={allVariants} disabled={active||busy} onChange={e=>setAllVariants(e.target.checked)}/> Include all nine ablations</label>
      <div className="research-actions"><button className="primary-button" disabled={!files.length||files.length>32||busy||active} onClick={()=>void start()}>Start batch evaluation</button>{active&&<button className="secondary-button" disabled={job?.status==='cancelling'} onClick={()=>void cancelJob(job!.id).then(setJob).catch(err=>setError(err.message))}>Cancel after current image</button>}</div>
      {job&&<div className="job-progress" role="status"><div><strong>{job.status}</strong><span>{job.completed} / {job.total} images processed · {job.successful} successful</span></div><progress max={job.total} value={job.completed}/>{job.error&&<p>{job.error}</p>}{job.failures?.map(item=><p key={item.key}>{item.key}: {item.error}</p>)}{job.download_url&&<button className="secondary-button" onClick={()=>void save(job.download_url!,'lumarestore-batch.zip')}><ArrowDownToLine size={14}/> Download images, CSV, JSON & plots</button>}</div>}
      {history.length>0&&<details className="parameters"><summary>Saved batch runs</summary><div className="history">{history.map(item=><button key={item.id} onClick={()=>void getJob(item.id).then(next=>{setJob(next);setSample('')}).catch(err=>setError(err.message))}><span>{new Date(item.created_at).toLocaleString()}</span><strong>{item.ablations?'Ablations':'Comparison'} · {item.status}</strong><span>{item.completed}/{item.total}</span></button>)}</div></details>}
      {error&&<p className="notice error" role="alert">{error}</p>}
    </section>
    {!!job?.report&&<BenchmarkViewer reportData={job?.report}/>}
    {keys.length>0&&<section className="panel padded"><div className="section-title"><h2>Batch comparison images</h2><select aria-label="Batch result image" value={chosen} onChange={e=>setSample(e.target.value)}>{keys.map(key=><option key={key}>{key}</option>)}</select></div><div className="artifact-grid">{report?.per_image?.filter(row=>row.key===chosen&&row.artifact).map(row=><figure className="panel artifact-card" key={row.mode}><img loading="lazy" src={artifactUrl(row.artifact!)} alt={`${row.key}: ${row.mode}`}/><figcaption>{row.mode.replaceAll('_',' ')}<button className="text-button" onClick={()=>void save(row.artifact!,`${row.mode}-${row.key}.png`)}>Download</button></figcaption></figure>)}</div></section>}
  </>
}
