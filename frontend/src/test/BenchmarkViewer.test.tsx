import { expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BenchmarkViewer from '../components/BenchmarkViewer'

vi.mock('recharts',()=>({
  ResponsiveContainer:()=> <div>Measured chart</div>,BarChart:()=>null,Bar:()=>null,
  CartesianGrid:()=>null,Tooltip:()=>null,XAxis:()=>null,YAxis:()=>null,
}))

it('imports actual report structure and preserves unavailable scores',async()=>{
  const user=userEvent.setup();render(<BenchmarkViewer/> )
  const report={partition:'test',ablations:true,protocol:'Synthetic software validation, no quality claim.',
    per_image:[{key:'scene',mode:'classical'}],unavailable:{},
    averages:{classical:{latency_ms:{mean:25.5,count:1,infinite_count:0},psnr:{mean:null,count:0,infinite_count:0}}}}
  const file=new File([JSON.stringify(report)],'report.json',{type:'application/json'})
  Object.defineProperty(file,'text',{value:async()=>JSON.stringify(report)})
  await user.upload(screen.getByLabelText('Import benchmark report'),file)
  expect(await screen.findByText('Ablation study')).toBeInTheDocument()
  expect(screen.getByText('25.5')).toBeInTheDocument()
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
  expect(screen.getByText('1 image')).toBeInTheDocument()
})

it('rejects a report with invented or invalid numeric encoding',async()=>{
  const user=userEvent.setup();render(<BenchmarkViewer/> )
  const text=JSON.stringify({partition:'test',protocol:'x',per_image:[{key:'x',mode:'x'}],
    averages:{x:{latency_ms:{mean:'not a score',count:1}}}})
  const file=new File([text],'bad.json',{type:'application/json'});Object.defineProperty(file,'text',{value:async()=>text})
  await user.upload(screen.getByLabelText('Import benchmark report'),file)
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid metric averages.')
})
