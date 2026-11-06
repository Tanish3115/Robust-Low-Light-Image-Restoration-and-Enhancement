import { afterEach, expect, it, vi } from 'vitest'
import { processImage,startBatch } from '../api'

afterEach(()=>vi.unstubAllGlobals())
it('sends the real multipart API contract',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({id:'result'}),{status:200}))
  vi.stubGlobal('fetch',fetch)
  const file=new File(['bytes'],'scene.png',{type:'image/png'})
  await processImage(file,'enhance','classical',.8,null,new AbortController().signal)
  const [url,options]=fetch.mock.calls[0]
  expect(url).toBe('/api/enhance');expect(options.body).toBeInstanceOf(FormData)
  expect(options.body.get('mode')).toBe('classical');expect(options.body.get('strength')).toBe('0.8')
  expect(options.headers).toBeUndefined()
})
it('surfaces model setup errors from the backend',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Checkpoint missing'}),{status:503})))
  await expect(processImage(new File(['x'],'x.png'),'enhance','deep',1,null,new AbortController().signal)).rejects.toThrow('Checkpoint missing')
})

it('sends vivid and 4K choices only for restoration',async()=>{
  const fetch=vi.fn().mockImplementation(()=>Promise.resolve(new Response(JSON.stringify({id:'result'}),{status:200})))
  vi.stubGlobal('fetch',fetch)
  const file=new File(['bytes'],'scene.png')
  await processImage(file,'enhance','auto',1,null,new AbortController().signal,{vivid:true,upscale4k:true})
  expect(fetch.mock.calls[0][1].body.get('vivid')).toBe('true')
  expect(fetch.mock.calls[0][1].body.get('upscale_4k')).toBe('true')
  await processImage(file,'compare','auto',1,null,new AbortController().signal,{vivid:true,upscale4k:true})
  expect(fetch.mock.calls[1][1].body.has('vivid')).toBe(false)
})

it('uses repeated multipart fields for batch inputs and aligned references',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({id:'job'}),{status:202}));vi.stubGlobal('fetch',fetch)
  const file=new File(['x'],'x.png',{type:'image/png'})
  await startBatch([file],[file],true)
  const [url,options]=fetch.mock.calls[0]
  expect(url).toBe('/api/jobs');expect(options.body.getAll('files')).toHaveLength(1)
  expect(options.body.getAll('references')).toHaveLength(1);expect(options.body.get('ablations')).toBe('true')
})
