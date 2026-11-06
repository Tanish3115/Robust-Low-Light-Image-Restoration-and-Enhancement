import { beforeEach,expect,it,vi } from 'vitest'
import { render,screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResearchWorkspace from '../components/ResearchWorkspace'
import { cancelJob,download,getJobs,runAblations,startBatch } from '../api'
import type { EvaluationJob,Result } from '../types'

vi.mock('../api',()=>({artifactUrl:(url:string)=>url,runAblations:vi.fn(),startBatch:vi.fn(),getJob:vi.fn(),getJobs:vi.fn(),cancelJob:vi.fn(),download:vi.fn()}))
vi.mock('../components/BenchmarkViewer',()=>({default:()=> <div>Measured experiment report</div>}))
beforeEach(()=>{vi.clearAllMocks();vi.mocked(getJobs).mockResolvedValue([]);vi.mocked(download).mockResolvedValue()})

it('executes actual ablation API wiring and exposes resulting images/exports',async()=>{
  const user=userEvent.setup();const file=new File(['image'],'scene.png',{type:'image/png'})
  vi.mocked(runAblations).mockResolvedValue({id:'abc',artifacts:{classical:'/classical.png'},comparisons:{classical:{metrics:{latency_ms:{value:15,available:true,direction:'lower'}}}}} as unknown as Result)
  render(<ResearchWorkspace file={file}/>);await user.click(screen.getByRole('button',{name:'Run all ablations'}))
  expect(await screen.findByAltText('classical ablation output')).toHaveAttribute('src','/classical.png')
  expect(runAblations).toHaveBeenCalledWith(file,null,expect.any(AbortSignal))
  await user.click(screen.getByRole('button',{name:'CSV'}));expect(download).toHaveBeenCalledWith('/api/results/abc/metrics','ablation-metrics.csv')
})

it('runs a selected batch and downloads its real server archive',async()=>{
  const user=userEvent.setup();const file=new File(['image'],'scene.png',{type:'image/png'})
  vi.mocked(startBatch).mockResolvedValue({id:'batch',status:'completed',total:1,completed:1,successful:1,ablations:false,created_at:'2026-11-06T00:00:00Z',download_url:'/batch.zip'} as EvaluationJob)
  render(<ResearchWorkspace file={null}/>);await user.upload(screen.getByLabelText('Batch input images'),file)
  await user.click(screen.getByRole('button',{name:'Start batch evaluation'}))
  expect(await screen.findByText(/1 \/ 1 images processed/)).toBeInTheDocument()
  expect(startBatch).toHaveBeenCalledWith([file],[],false)
  await user.click(screen.getByRole('button',{name:/Download images/}));expect(download).toHaveBeenCalledWith('/batch.zip','lumarestore-batch.zip')
})

it('lets the user cancel a queued run',async()=>{
  const user=userEvent.setup();const file=new File(['image'],'scene.png',{type:'image/png'})
  const queued={id:'queued',status:'queued',total:1,completed:0,successful:0,ablations:false,created_at:'2026-11-06T00:00:00Z'} as EvaluationJob
  vi.mocked(startBatch).mockResolvedValue(queued);vi.mocked(cancelJob).mockResolvedValue({...queued,status:'cancelled'})
  render(<ResearchWorkspace file={null}/>);await user.upload(screen.getByLabelText('Batch input images'),file)
  await user.click(screen.getByRole('button',{name:'Start batch evaluation'}))
  await user.click(await screen.findByRole('button',{name:'Cancel after current image'}))
  expect(cancelJob).toHaveBeenCalledWith('queued');expect(await screen.findByText('cancelled')).toBeInTheDocument()
})
