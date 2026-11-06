import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Analysis, Comparison } from '../types'

export function Histogram({analysis}: {analysis: Analysis}) {
  return <div className="chart" role="img" aria-label="Measured luminance histogram"><ResponsiveContainer width="100%" height="100%"><AreaChart data={analysis.histogram} margin={{top:10,right:12,bottom:0,left:0}}><defs><linearGradient id="histfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#56d9db" stopOpacity={.4}/><stop offset="100%" stopColor="#56d9db" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#24313e"/><XAxis dataKey="bin" tick={{fill:'#8194a5',fontSize:11}} tickCount={5} tickFormatter={v=>String(Math.round(v))}/><YAxis tick={{fill:'#8194a5',fontSize:11}} width={45}/><Tooltip contentStyle={{background:'#151e29',border:'1px solid #2c3c4a',borderRadius:8}}/><Area type="monotone" dataKey="count" name="Pixels" stroke="#56d9db" fill="url(#histfill)"/></AreaChart></ResponsiveContainer></div>
}

export function LatencyChart({comparisons}: {comparisons: Record<string,Comparison>}) {
  const data = Object.entries(comparisons).filter(([,v])=>v.metrics).map(([mode,v])=>({mode,ms: v.metrics!.latency_ms.value}))
  return <div className="chart" role="img" aria-label="Measured pipeline latency"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{top:10,right:16,bottom:0,left:0}}><CartesianGrid vertical={false} stroke="#24313e"/><XAxis dataKey="mode" tick={{fill:'#8194a5',fontSize:12}}/><YAxis width={55} tick={{fill:'#8194a5',fontSize:11}}/><Tooltip contentStyle={{background:'#151e29',border:'1px solid #2c3c4a',borderRadius:8}}/><Bar dataKey="ms" name="Milliseconds" fill="#56d9db" radius={[5,5,0,0]} maxBarSize={70}/></BarChart></ResponsiveContainer></div>
}
