import { useEffect, useState } from 'react'
import { FileJson, Upload } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Average { mean:number|null;count:number;infinite_count:number }
interface Report {
  partition:string;ablations:boolean;protocol:string;
  per_image:{key:string;mode:string}[];
  averages:Record<string,Record<string,Average>>;
  unavailable:Record<string,string>;
  dataset?:{name:string};
}
const indicators:Record<string,string>={psnr:'PSNR ↑',ssim:'SSIM ↑',lpips:'LPIPS ↓',niqe:'NIQE ↓',noise_suppression:'Noise reduction ↑',edge_preservation:'Gradient correlation ↑',latency_ms:'Latency (ms) ↓'}

function parseReport(text:string):Report {
  const report=JSON.parse(text) as Report
  if(!report || !Array.isArray(report.per_image) || !report.averages || typeof report.averages!=='object'
    || typeof report.partition!=='string' || typeof report.protocol!=='string')throw new Error('Choose a LumaRestore benchmark report.json file.')
  if(!report.per_image.length || !Object.keys(report.averages).length)throw new Error('This report has no completed measurements.')
  for(const row of report.per_image)if(!row||typeof row.key!=='string'||typeof row.mode!=='string')throw new Error('Invalid per-image records.')
  if(report.dataset && typeof report.dataset.name!=='string')throw new Error('Invalid dataset metadata.')
  if(report.unavailable && (typeof report.unavailable!=='object'||Object.values(report.unavailable).some(reason=>typeof reason!=='string')))throw new Error('Invalid unavailable-method records.')
  for(const group of Object.values(report.averages)) {
    if(!group||typeof group!=='object'||!group.latency_ms)throw new Error('Invalid method averages.')
    for(const item of Object.values(group))if(!item||!(item.mean===null||Number.isFinite(item.mean))||!Number.isInteger(item.count)||item.count<0)throw new Error('Invalid metric averages.')
  }
  return report
}

export default function BenchmarkViewer({reportData}:{reportData?:unknown}={}) {
  const [report,setReport]=useState<Report|null>(null)
  const [error,setError]=useState('')
  const [filename,setFilename]=useState('')
  useEffect(()=>{
    if(reportData){try{setReport(parseReport(JSON.stringify(reportData)));setFilename('Completed evaluation')}catch(err){setError((err as Error).message)}}
  },[reportData])
  async function load(file?:File) {
    if(!file)return
    setError('')
    try {
      if(file.size>20*1024**2)throw new Error('Choose a report smaller than 20 MB.')
      const next=parseReport(await file.text());setReport(next);setFilename(file.name)
    } catch(err){setError(err instanceof Error?err.message:'Unable to read this report.')}
  }
  const data=report?Object.entries(report.averages).map(([mode,metrics])=>({mode:mode.replaceAll('_',' '),ms:metrics.latency_ms.mean})):[]
  const imageCount=report?new Set(report.per_image.map(row=>row.key)).size:0
  return <section className="panel padded benchmark-viewer">
    <div className="section-title"><div><h2>Benchmarks & ablation studies</h2><p className="caption">Import a completed evaluation report to explore measured method averages.</p></div><label className="secondary-button reference-picker"><Upload size={14}/> Import report<input aria-label="Import benchmark report" type="file" accept=".json,application/json" onChange={e=>{void load(e.target.files?.[0]);e.target.value=''}}/></label></div>
    {error&&<p className="notice error" role="alert">{error}</p>}
    {report?<>
      <div className="benchmark-summary"><span>{report.dataset?.name??"Custom dataset"}</span><span className="tag">{report.ablations?'Ablation study':'Benchmark run'}</span><span>{imageCount} image{imageCount===1?'':'s'}</span><span>{Object.keys(report.averages).length} methods</span><span>{report.partition} partition</span><span>{filename}</span></div>
      <div style={{height:Math.max(180,data.length*38+30)}} role="img" aria-label="Imported measured mean latency"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{top:15,bottom:5,left:0,right:25}}><CartesianGrid horizontal={false} stroke="#24313e"/><XAxis type="number" tick={{fill:'#8194a5',fontSize:10}}/><YAxis type="category" dataKey="mode" width={125} tick={{fill:'#92acbd',fontSize:10}}/><Tooltip contentStyle={{background:'#151e29',border:'1px solid #2c3c4a',borderRadius:8}}/><Bar dataKey="ms" name="Mean milliseconds" fill="#56d9db" radius={[0,4,4,0]} maxBarSize={18}/></BarChart></ResponsiveContainer></div>
      <div className="table-scroll"><table><thead><tr><th>Method</th>{Object.values(indicators).map(name=><th key={name}>{name}</th>)}</tr></thead><tbody>{Object.entries(report.averages).map(([mode,metrics])=><tr key={mode}><td>{mode.replaceAll('_',' ')}</td>{Object.keys(indicators).map(name=>{const item=metrics[name];return <td key={name} title={`${item?.count??0} finite measurement(s); ${item?.infinite_count??0} infinite`}>{item?.mean!=null?item.mean.toLocaleString(undefined,{maximumFractionDigits:item.mean>10?1:4}):item?.infinite_count?'∞':'Unavailable'}</td>})}</tr>)}</tbody></table></div>
      <p className="caption">{report.protocol}</p>{Object.keys(report.unavailable??{}).length>0&&<details className="parameters"><summary>Unavailable experiments</summary><ul className="notes-list">{Object.entries(report.unavailable).map(([mode,reason])=><li key={mode}>{mode}: {reason}</li>)}</ul></details>}
    </>:<div className="benchmark-empty"><FileJson size={23}/><p>No benchmark report loaded. Results appear only after you import measurements from an actual run.</p></div>}
  </section>
}
