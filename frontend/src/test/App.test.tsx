import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App, { metricText } from '../App'
import { download, getModels, processImage } from '../api'
import type { ModelResponse, Result } from '../types'

vi.mock('../api',()=>({getModels:vi.fn(),processImage:vi.fn(),download:vi.fn(),artifactUrl:(url:string)=>url,
  getJobs:vi.fn().mockResolvedValue([]),getBenchmarks:vi.fn().mockResolvedValue([])}))
vi.mock('../components/ImageCompare',()=>({default:({enhanced}:{enhanced?:string})=><div aria-label="Image viewer">{enhanced?'Restored comparison':'Original preview'}</div>}))
vi.mock('../components/Charts',()=>({Histogram:()=> <div>Histogram</div>,LatencyChart:()=> <div>Latency</div>}))
const models:ModelResponse = {models:{auto:{available:true,label:'Auto'},classical:{available:true,label:'Classical'},deep:{available:false,label:'Deep',reason:'Checkpoint missing'},hybrid:{available:false,label:'Hybrid',reason:'Checkpoint missing'}},limits:{upload_mb:20,input_pixels:40000000,process_side:2048},iqa_enabled:false}
const result:Result={id:'abc',kind:'enhance',created_at:'2026-11-06T00:00:00Z',requested_mode:'classical',executed_mode:'classical',latency_ms:45,image:{original_size:[128,96],processed_size:[128,96],format:'PNG',resized:false},analysis:{mean_brightness:.1,median_luminance:.1,dark_pixel_percentage:75,underexposure_severity:.8,classification:'severely underexposed',illumination_variance:.01,nonuniform_illumination:.3,noise_estimate:.01,edge_density:.1,texture_strength:.02,local_contrast:.03,dynamic_range:.5,colour_imbalance:.1,saturation:.3,highlight_clipping:0,shadow_clipping:0,channel_means:[.1,.1,.1],histogram:[],noise_protocol:'test protocol'},artifacts:{original:'/original.png',enhanced:'/enhanced.png'},metrics:{latency_ms:{value:45,available:true,direction:'lower'}},diagnostics:[],parameters:{gamma:.5},comparisons:{},notices:[],controller:null}

beforeEach(()=>{vi.clearAllMocks();vi.mocked(getModels).mockResolvedValue(models);vi.mocked(processImage).mockResolvedValue(result);vi.mocked(download).mockResolvedValue()})

describe('working restoration studio',()=>{
  it('uploads, executes the selected mode, displays output, and downloads',async()=>{
    const user=userEvent.setup();render(<App/>);await screen.findByText('Backend connected')
    await user.upload(screen.getByLabelText('Upload image'),new File(['image'],'dark.png',{type:'image/png'}))
    expect(screen.getByText('Original preview')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:/^Classical/}))
    await user.click(screen.getByRole('button',{name:'Enhance image'}))
    await screen.findByText('Restored comparison')
    expect(processImage).toHaveBeenCalledWith(expect.any(File),'enhance','classical',1,null,expect.any(AbortSignal),{vivid:true,upscale4k:false})
    await user.click(screen.getByRole('button',{name:'Download PNG'}))
    expect(download).toHaveBeenCalledWith('/enhanced.png','lumarestore-classical.png')
    await user.click(screen.getByRole('button',{name:'Reset'}))
    expect(screen.getByRole('button',{name:'Browse images'})).toBeInTheDocument()
  })
  it('keeps missing neural modes disabled and shows processing errors',async()=>{
    const user=userEvent.setup();render(<App/>);await screen.findByText('Backend connected')
    expect(screen.getByRole('button',{name:/^Deep learning/})).toBeDisabled()
    expect(screen.getByRole('button',{name:/^Adaptive hybrid/})).toBeDisabled()
    vi.mocked(processImage).mockRejectedValueOnce(new Error('Invalid image data'))
    await user.upload(screen.getByLabelText('Upload image'),new File(['x'],'bad.png',{type:'image/png'}))
    await user.click(screen.getByRole('button',{name:'Enhance image'}))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid image data')
  })
  it('shows a loading indicator and prevents duplicate work',async()=>{
    let finish!:(result:Result)=>void
    vi.mocked(processImage).mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    const user=userEvent.setup();render(<App/>);await screen.findByText('Backend connected')
    await user.upload(screen.getByLabelText('Upload image'),new File(['x'],'dark.png',{type:'image/png'}))
    await user.click(screen.getByRole('button',{name:'Enhance image'}))
    expect(screen.getByRole('button',{name:'Processing…'})).toBeDisabled()
    expect(screen.getByText('Restoring your image')).toBeInTheDocument()
    finish(result);await waitFor(()=>expect(screen.getByRole('button',{name:'Enhance image'})).toBeEnabled())
  })
  it('keeps unsupported reference scores unavailable',()=>{
    expect(metricText({value:null,available:false,direction:'higher'})).toBe('Unavailable')
    expect(metricText({value:null,available:true,infinite:true,direction:'higher'})).toBe('∞')
  })
  it('navigates all six workspace views with accessible names',async()=>{
    const user=userEvent.setup();render(<App/>);await screen.findByText('Backend connected')
    for(const page of ['Image analyzer','Pipeline explorer','Model comparison','Performance analytics','Quality diagnostics','Restoration studio']) {
      await user.click(screen.getByRole('button',{name:page}));expect(screen.getByRole('heading',{level:1,name:page})).toBeInTheDocument()
    }
  })
  it('closes setup notes with Escape and restores keyboard focus',async()=>{
    const user=userEvent.setup();render(<App/>);const opener=screen.getByRole('button',{name:'Setup & evaluation notes'})
    await user.click(opener);expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}');expect(screen.queryByRole('dialog')).not.toBeInTheDocument();expect(opener).toHaveFocus()
  })
})
