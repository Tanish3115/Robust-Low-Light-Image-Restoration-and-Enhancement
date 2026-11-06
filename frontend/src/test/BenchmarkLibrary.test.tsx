import { expect,it,vi } from 'vitest'
import { render,screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BenchmarkLibrary from '../components/BenchmarkLibrary'
import { download,getBenchmark,getBenchmarks } from '../api'

vi.mock('../api',()=>({artifactUrl:(url:string)=>url,download:vi.fn(),getBenchmark:vi.fn(),getBenchmarks:vi.fn()}))
vi.mock('../components/BenchmarkViewer',()=>({default:()=> <div>Measured dataset report</div>}))

it('loads completed server measurements and their actual image/archive routes',async()=>{
  vi.mocked(getBenchmarks).mockResolvedValue([{id:'official-run',created_at:'2026-11-06T00:00:00Z',partition:'test',images:15,methods:3,ablations:false}])
  vi.mocked(getBenchmark).mockResolvedValue({per_image:[{key:'scene',mode:'deep',artifact:'/measured.png'}]})
  vi.mocked(download).mockResolvedValue()
  const user=userEvent.setup();render(<BenchmarkLibrary/> )
  expect(await screen.findByAltText('Benchmark scene: deep')).toHaveAttribute('src','/measured.png')
  expect(screen.getByText('Measured dataset report')).toBeInTheDocument()
  await user.click(screen.getByRole('button',{name:'Download complete run'}))
  expect(download).toHaveBeenCalledWith('/api/benchmarks/official-run/download','official-run.zip')
})
