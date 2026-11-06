import { useMemo,useState } from 'react'
import { artifactUrl } from '../api'
import type { Region,Result } from '../types'
import ImageCompare from './ImageCompare'

export default function RegionInspector({result}:{result:Result}) {
  const [selected,setSelected]=useState('full')
  const regions=useMemo(()=>{
    const items:{key:string;label:string;region?:Region}[]=[{key:'full',label:'Full image'},
      {key:'centre',label:'Centre detail',region:{x:.25,y:.25,width:.5,height:.5}},
      {key:'top_left',label:'Top-left detail',region:{x:0,y:0,width:.5,height:.5}},
      {key:'top_right',label:'Top-right detail',region:{x:.5,y:0,width:.5,height:.5}},
      {key:'bottom_left',label:'Bottom-left detail',region:{x:0,y:.5,width:.5,height:.5}},
      {key:'bottom_right',label:'Bottom-right detail',region:{x:.5,y:.5,width:.5,height:.5}}]
    result.diagnostics.forEach((item,index)=>{if(item.region)items.push({key:`risk-${index}`,label:`Detected: ${item.problem}`,region:item.region})})
    return items
  },[result])
  const region=regions.find(item=>item.key===selected)?.region
  return <section className="panel"><div className="panel-heading"><h2>Inspect before / after regions</h2><select aria-label="Inspection region" value={selected} onChange={e=>setSelected(e.target.value)}>{regions.map(item=><option key={item.key} value={item.key}>{item.label}</option>)}</select></div><ImageCompare original={artifactUrl(result.artifacts.original)} enhanced={artifactUrl(result.artifacts.enhanced)} region={region}/></section>
}
