import { useEffect,useState } from 'react'
import { ArrowDownToLine,RefreshCw } from 'lucide-react'
import { artifactUrl,download,getBenchmark,getBenchmarks } from '../api'
import type { BenchmarkSummary } from '../api'
import BenchmarkViewer from './BenchmarkViewer'

interface DisplayReport {per_image?:{key:string;mode:string;artifact?:string;original?:string}[]}

export default function BenchmarkLibrary() {
  const [reports,setReports]=useState<BenchmarkSummary[]>([])
  const [selected,setSelected]=useState('')
  const [record,setRecord]=useState<unknown>(null)
  const [sample,setSample]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function refresh() {
    setBusy(true);setError('')
    try{const items=await getBenchmarks();setReports(items);if(items.length)setSelected(current=>items.some(item=>item.id===current)?current:(items.find(item=>item.partition==='test'&&!item.ablations&&item.methods>=3)??items[0]).id)}catch(err){setError((err as Error).message)}finally{setBusy(false)}
  }
  useEffect(()=>{void refresh()},[])
  useEffect(()=>{
    if(!selected)return
    let active=true;setRecord(null);setSample('')
    void getBenchmark(selected).then(data=>{if(active)setRecord(data)}).catch(err=>{if(active)setError(err.message)})
    return()=>{active=false}
  },[selected])
  async function save(url:string,name:string){try{await download(url,name)}catch(err){setError((err as Error).message)}}
  const report=record as DisplayReport|null
  const keys=[...new Set(report?.per_image?.map(row=>row.key)??[])]
  const chosen=sample||keys[0]
  return <><section className="panel padded"><div className="section-title"><h2>Completed dataset benchmarks</h2><button className="text-button" disabled={busy} onClick={()=>void refresh()}><RefreshCw size={14}/> Refresh reports</button></div><p className="body-copy">Browse completed runs saved by this backend. Each report retains its measured scores, image count, model configuration, and evaluation partition.</p>
    {reports.length>0?<div className="research-actions"><select aria-label="Saved dataset benchmark" value={selected} onChange={e=>setSelected(e.target.value)}>{reports.map(item=><option key={item.id} value={item.id}>{item.id} · {item.images} images · {item.methods} methods</option>)}</select><button className="secondary-button" onClick={()=>void save(`/api/benchmarks/${selected}/download`,`${selected}.zip`)}><ArrowDownToLine size={14}/> Download complete run</button><button className="text-button" onClick={()=>void save(`/api/benchmarks/${selected}/artifacts/averages.csv`,'dataset-averages.csv')}>Average metrics CSV</button></div>:<p className="caption">No completed dataset runs were found. You can run an uploaded batch below or import a saved report.</p>}
    {error&&<p className="notice error" role="alert">{error}</p>}</section>
    {!!record&&<BenchmarkViewer reportData={record}/>}
    {keys.length>0&&<section className="panel padded"><div className="section-title"><h2>Measured comparison images</h2><select aria-label="Benchmark image" value={chosen} onChange={e=>setSample(e.target.value)}>{keys.map(key=><option key={key}>{key}</option>)}</select></div><div className="artifact-grid">{report?.per_image?.filter(row=>row.key===chosen&&row.artifact).map(row=><figure className="panel artifact-card" key={row.mode}><img loading="lazy" src={artifactUrl(row.artifact!)} alt={`Benchmark ${row.key}: ${row.mode}`}/><figcaption>{row.mode.replaceAll('_',' ')}</figcaption></figure>)}</div></section>}
  </>
}
