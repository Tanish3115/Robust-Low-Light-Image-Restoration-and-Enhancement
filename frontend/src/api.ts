import type { Mode, ModelResponse, Result, EvaluationJob } from './types'

const base = (import.meta as ImportMeta & {env: Record<string,string>}).env.VITE_API_URL?.replace(/\/$/, '') ?? ''
export const artifactUrl = (url: string) => `${base}${url}`

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export async function getModels(): Promise<ModelResponse> {
  return parse(await fetch(`${base}/api/models`))
}

export async function processImage(file: File, endpoint: 'enhance' | 'analyze' | 'compare' | 'evaluate', mode: Mode,
                                   strength: number, reference: File | null, signal: AbortSignal,
                                   finish?: {vivid:boolean; upscale4k:boolean}): Promise<Result> {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  form.append('strength', String(strength))
  if (endpoint==='enhance' && finish) {
    form.append('vivid',String(finish.vivid))
    form.append('upscale_4k',String(finish.upscale4k))
  }
  if (reference && ['compare', 'evaluate'].includes(endpoint)) form.append('reference', reference)
  return parse(await fetch(`${base}/api/${endpoint}`, {method: 'POST', body: form, signal}))
}

export async function download(url: string, filename: string) {
  const response = await fetch(artifactUrl(url))
  if (!response.ok) throw new Error('The artifact is unavailable or has expired. Process the image again.')
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export async function runAblations(file:File,reference:File|null,signal:AbortSignal):Promise<Result> {
  const body=new FormData();body.append('file',file);if(reference)body.append('reference',reference)
  return parse(await fetch(`${base}/api/ablate`,{method:'POST',body,signal}))
}
export async function startBatch(files:File[],references:File[],ablations:boolean):Promise<EvaluationJob> {
  const body=new FormData();files.forEach(file=>body.append('files',file));references.forEach(file=>body.append('references',file));body.append('ablations',String(ablations))
  return parse(await fetch(`${base}/api/jobs`,{method:'POST',body}))
}
export async function getJob(id:string,signal?:AbortSignal):Promise<EvaluationJob> {
  return parse(await fetch(`${base}/api/jobs/${encodeURIComponent(id)}`,{signal}))
}
export async function getJobs():Promise<EvaluationJob[]> {return parse(await fetch(`${base}/api/jobs`))}
export async function cancelJob(id:string):Promise<EvaluationJob> {return parse(await fetch(`${base}/api/jobs/${encodeURIComponent(id)}/cancel`,{method:'POST'}))}
export interface BenchmarkSummary {id:string;created_at:string;partition:string;ablations:boolean;images:number;methods:number}
export async function getBenchmarks():Promise<BenchmarkSummary[]> {return parse(await fetch(`${base}/api/benchmarks`))}
export async function getBenchmark(id:string):Promise<unknown> {return parse(await fetch(`${base}/api/benchmarks/${encodeURIComponent(id)}`))}
