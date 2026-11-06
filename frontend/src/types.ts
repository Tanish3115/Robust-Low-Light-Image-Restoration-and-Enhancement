export type Mode = 'auto' | 'classical' | 'deep' | 'hybrid'
export type Page = 'studio' | 'analyzer' | 'pipeline' | 'comparison' | 'analytics' | 'quality'
export interface Model { available: boolean; label: string; reason?: string; device?: string }
export interface ModelResponse { models: Record<Mode, Model>; limits: {upload_mb: number; input_pixels: number; process_side: number}; iqa_enabled: boolean }
export interface Metric { value: number | null; direction: string; available: boolean; reason?: string; infinite?: boolean }
export interface Region { x:number;y:number;width:number;height:number }
export interface Diagnostic { code: string; problem: string; stage: string; action: string; limitation: string; region?:Region; risk_map?:string;affected_fraction?:number }
export interface EvaluationJob {
  id:string;status:'queued'|'running'|'cancelling'|'cancelled'|'completed'|'failed'|'interrupted';
  total:number;completed:number;successful:number;ablations:boolean;created_at:string;
  failures?:{key:string;error:string}[];error?:string|null;report?:unknown;download_url?:string;
}
export interface Analysis {
  mean_brightness: number; median_luminance: number; dark_pixel_percentage: number;
  underexposure_severity: number; classification: string; illumination_variance: number;
  nonuniform_illumination: number; noise_estimate: number; edge_density: number;
  texture_strength: number; local_contrast: number; dynamic_range: number; colour_imbalance: number;
  saturation: number; highlight_clipping: number; shadow_clipping: number; channel_means: number[];
  histogram: { bin: number; count: number }[]; noise_protocol: string;
}
export interface Comparison { metrics?: Record<string, Metric>; parameters?: object; diagnostics?: Diagnostic[]; artifact?: string; unavailable?: boolean; reason?: string }
export interface Result {
  id: string; kind: string; created_at: string; requested_mode: string; executed_mode: string; latency_ms: number;
  image: { original_size: number[]; processed_size: number[]; format: string; resized: boolean };
  analysis: Analysis; artifacts: Record<string,string>; metrics: Record<string, Metric>; diagnostics: Diagnostic[];
  parameters: object; comparisons: Record<string, Comparison>; notices: string[];
  controller: { selected_mode: string; explanation: string; deep_contribution: number; classical_contribution: number; candidate_scores: Record<string,number>; warnings: string[] } | null;
}
