"""Measurable artifact-risk proxies and bounded, reference-free corrections.

These detectors flag risks, not semantic truth. In particular, edge-ring energy
can be legitimate texture; it is never labelled a confirmed halo.
"""
import cv2
import numpy as np

from backend.src.utils.images import guided_filter, luminance


def assess_artifacts(original: np.ndarray, candidate: np.ndarray) -> tuple[list[dict], dict]:
    h,w=original.shape[:2];scale=min(1.,512/max(h,w))
    size=(max(1,round(w*scale)),max(1,round(h*scale)))
    source=cv2.resize(original,size,interpolation=cv2.INTER_AREA)
    output=cv2.resize(candidate,size,interpolation=cv2.INTER_AREA)
    a,b=luminance(source),luminance(output)
    gradient=lambda x:np.hypot(cv2.Sobel(x,cv2.CV_32F,1,0),cv2.Sobel(x,cv2.CV_32F,0,1))/4
    ga,gb=gradient(a),gradient(b)
    gain=np.clip(cv2.GaussianBlur(b,(0,0),3)/np.maximum(cv2.GaussianBlur(a,(0,0),3),.025),.5,6)
    edge=(ga>max(.035,float(np.percentile(ga,90)))).astype(np.float32)
    ring=np.clip(cv2.dilate(edge,np.ones((9,9),np.uint8))-cv2.dilate(edge,np.ones((3,3),np.uint8)),0,1)
    band=lambda x:cv2.GaussianBlur(x,(0,0),1)-cv2.GaussianBlur(x,(0,0),3)
    halo=np.clip((np.abs(band(b)-gain*band(a))-.035)/.09,0,1)*ring
    detail=np.clip((.55*ga*gain-gb)/np.maximum(ga*gain,.025),0,1)*(ga>.035)
    residual=lambda x:np.abs(x-cv2.GaussianBlur(x,(0,0),1))
    noise=np.clip((residual(b)-gain*residual(a)-.02)/.08,0,1)*np.exp(-ga*50)
    ca=source/np.maximum(source.sum(axis=2,keepdims=True),.04)
    cb=output/np.maximum(output.sum(axis=2,keepdims=True),.04)
    colour=np.clip((np.mean(np.abs(cb-ca),axis=2)-.08)/.15,0,1)*(a>.04)
    clipping=((output.max(axis=2)>.995)&(source.max(axis=2)<.9)).astype(np.float32)
    local_std=lambda x:np.sqrt(np.maximum(cv2.GaussianBlur(x*x,(0,0),3)-cv2.GaussianBlur(x,(0,0),3)**2,0))
    contrast=np.clip((local_std(b)-np.maximum(local_std(a)*gain*2.5,.20))/.15,0,1)
    maps={'halo_risk':halo,'detail_loss_map':detail,'noise_amplification_map':noise,
          'colour_shift_map':colour,'new_clipping_map':clipping,'contrast_risk':contrast}
    maps['artifact_risk']=np.maximum.reduce(list(maps.values())).astype(np.float32)
    warnings=[]
    labels={'halo_risk':('edge_ring_risk','Elevated edge-ring overshoot risk.','Illumination / contrast','Fine edge-adjacent texture can trigger this proxy.'),
            'detail_loss_map':('local_detail_loss','Local gradient loss relative to the input.','Denoising / reconstruction','Input-relative gradients do not establish true texture fidelity.'),
            'noise_amplification_map':('local_noise_risk','Elevated flat-region residual energy.','Illumination / denoising','Newly revealed texture can resemble noise.'),
            'colour_shift_map':('local_colour_shift','Local chromaticity changed substantially.','Colour reconstruction','An original scene cast may be intentional or may itself need correction.'),
            'new_clipping_map':('new_local_clipping','Previously unclipped pixels approach saturation.','Exposure','Lost input highlights cannot be reconstructed.'),
            'contrast_risk':('excess_local_contrast','Local contrast is unusually high after exposure normalization.','Local contrast','Strong scene texture may be valid.')}
    for name,risk in maps.items():
        if name not in labels:continue
        fraction=float(np.mean(risk>.35))
        if fraction<.002:continue
        code,problem,stage,limitation=labels[name]
        yy,xx=np.nonzero(risk>.35)
        region={'x':float(xx.min()/risk.shape[1]),'y':float(yy.min()/risk.shape[0]),
                'width':float((xx.max()-xx.min()+1)/risk.shape[1]),'height':float((yy.max()-yy.min()+1)/risk.shape[0])}
        warnings.append({'code':code,'problem':problem,'stage':stage,'action':'Region flagged for inspection.',
                         'limitation':limitation,'region':region,'risk_map':name,'affected_fraction':fraction})
    return warnings,maps


def suppress_artifacts(original: np.ndarray, candidate: np.ndarray) -> tuple[np.ndarray,list[dict],dict]:
    warnings,maps=assess_artifacts(original,candidate)
    if not warnings:return candidate,[],maps
    h,w=original.shape[:2];y=luminance(original)
    mask=lambda key:cv2.resize(maps[key],(w,h),interpolation=cv2.INTER_LINEAR)[:,:,None]
    output=candidate.copy()
    actions=[]
    if any(item['code'] in {'edge_ring_risk','local_noise_risk','excess_local_contrast'} for item in warnings):
        smooth=np.stack([guided_filter(y,output[:,:,c],radius=6,eps=.002) for c in range(3)],axis=2)
        weight=np.maximum.reduce([mask('halo_risk')*.35,mask('noise_amplification_map')*.4,mask('contrast_risk')*.3])
        output=output*(1-weight)+smooth*weight
        actions.append('Applied bounded edge-aware residual/contrast suppression in detected risk regions.')
    if any(item['code']=='local_colour_shift' for item in warnings):
        preserved=np.clip(original*np.minimum(luminance(output)/np.maximum(y,.025),6)[:,:,None],0,1)
        weight=mask('colour_shift_map')*.3
        output=output*(1-weight)+preserved*weight
        actions.append('Reduced chromaticity drift toward the input direction at the restored luminance.')
    if any(item['code']=='local_detail_loss' for item in warnings):
        detail=original-cv2.GaussianBlur(original,(0,0),1)
        output=np.clip(output+detail*mask('detail_loss_map')*.2,0,1)
        actions.append('Restored a bounded input high-frequency residual around lost strong edges.')
    if any(item['code']=='new_local_clipping' for item in warnings):
        peak=output.max(axis=2,keepdims=True)
        compressed=.94+.055*np.tanh(np.maximum(peak-.94,0)/.055)
        toned=output*np.minimum(1,compressed/np.maximum(peak,1e-6))
        weight=mask('new_clipping_map')
        output=output*(1-weight)+toned*weight
        actions.append('Compressed newly clipped highlights with a bounded shoulder curve.')
    for warning in warnings:warning['action']=' '.join(actions)
    protection=np.clip((y-.70)/.28,0,1)[:,:,None]
    output=output*(1-protection)+original*protection
    return np.clip(output,0,1).astype(np.float32),warnings,maps
