import io
import time
import zipfile

import numpy as np

from backend.src.evaluation.artifacts import assess_artifacts,suppress_artifacts


def finish(client,job_id):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        response=client.get(f'/api/jobs/{job_id}');assert response.status_code==200
        record=response.json()
        if record['status'] not in {'queued','running','cancelling'}:return record
        time.sleep(.03)
    raise AssertionError('Evaluation did not finish.')


def test_real_web_ablation_outputs(client,png):
    response=client.post('/api/ablate',files={'file':('image.png',png)})
    assert response.status_code==200,response.text
    record=response.json()
    assert len([item for item in record['comparisons'].values() if item.get('metrics')])==4
    assert record['comparisons']['deep']['unavailable']
    assert client.get(record['artifacts']['retinex_only']).status_code==200


def test_batch_progress_reports_and_archive(client,png):
    response=client.post('/api/jobs',files=[('files',('a.png',png)),('files',('b.png',png)),('references',('a.png',png)),('references',('b.png',png))])
    assert response.status_code==202,response.text
    job=finish(client,response.json()['id'])
    assert job['status']=='completed' and job['completed']==2 and job['successful']==2
    assert len(job['report']['per_image'])==2
    assert job['report']['averages']['classical']['ssim']['count']==2
    archive=client.get(job['download_url']);assert archive.status_code==200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as files:
        assert {'report.json','metrics.csv','averages.csv','latency.svg','quality.svg'}<=set(files.namelist())
    artifact=job['report']['per_image'][0]['artifact']
    assert client.get(artifact).content.startswith(b'\x89PNG')
    assert client.get('/api/jobs').json()[0]['id']==job['id']
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()['status']=='completed'


def test_batch_rejects_ambiguous_pairing_and_tracks_actual_failures(client,png):
    response=client.post('/api/jobs',files=[('files',('a.png',png)),('references',('b.png',png))])
    assert response.status_code==422
    response=client.post('/api/jobs',files=[('files',('invalid.png',b'invalid'))])
    job=finish(client,response.json()['id'])
    assert job['status']=='failed' and job['successful']==0
    assert job['failures'][0]['key']=='invalid.png'
    assert client.get('/api/jobs/not-a-uuid').status_code==404
    assert client.get(f"/api/jobs/{job['id']}/artifacts/inputs.json").status_code==404


def test_artifact_corrections_are_bounded_and_preserve_original_highlights():
    original=np.full((96,128,3),.15,np.float32);original[:,64:]=.45;original[:10,:10]=1
    output=np.minimum(original*2,1);output[25:75,55:64]=1;output[40:70,10:40]=[.9,.1,.1]
    observations,maps=assess_artifacts(original,output)
    assert observations and maps['artifact_risk'].max()>0
    assert all('region' in item for item in observations)
    corrected,actions,_=suppress_artifacts(original,output)
    assert np.isfinite(corrected).all() and corrected.min()>=0 and corrected.max()<=1
    assert np.allclose(corrected[:10,:10],1)
    assert not np.array_equal(corrected,output)
    assert actions[0]['action']!='Region flagged for inspection.'


def test_chunked_uploads_cannot_bypass_body_limit(client):
    import backend.app.main as module
    module.settings.max_upload_mb=1
    response=client.post('/api/analyze',content=iter([b'x'*(1024*1024)]*3),headers={'Content-Type':'application/octet-stream'})
    assert response.status_code==413


def test_queued_job_can_be_cancelled_without_fabricated_measurements(client,png):
    import backend.app.main as module
    module.service.gate.acquire()
    try:
        response=client.post('/api/jobs',files=[('files',('a.png',png))]);assert response.status_code==202
        job_id=response.json()['id']
        assert client.post(f'/api/jobs/{job_id}/cancel').json()['status']=='cancelling'
    finally:module.service.gate.release()
    job=finish(client,job_id)
    assert job['status']=='cancelled' and job['completed']==0
    assert job['report']['per_image']==[]


def test_completed_cli_reports_are_browsable_and_downloadable(client,dark_rgb):
    import backend.app.main as module
    from backend.src.classical.pipeline import enhance_classical
    from backend.src.evaluation.metrics import evaluate
    from backend.src.evaluation.reporting import write_report
    from backend.src.utils.images import to_uint8
    from PIL import Image
    output=module.service.store.root/'measured-benchmark';(output/'00000').mkdir(parents=True)
    candidate=enhance_classical(dark_rgb)
    Image.fromarray(to_uint8(candidate.image)).save(output/'00000/classical.png')
    rows=[{'key':'scene','mode':'classical','metrics':evaluate(dark_rgb,candidate.image,latency_ms=candidate.latency_ms)}]
    write_report(output,rows,model={},settings={})
    assert client.get('/api/benchmarks').json()[0]['id']=='measured-benchmark'
    report=client.get('/api/benchmarks/measured-benchmark').json()
    assert client.get(report['per_image'][0]['artifact']).status_code==200
    assert client.get('/api/benchmarks/measured-benchmark/download').status_code==200
    assert client.get('/api/benchmarks/measured-benchmark/artifacts/unknown.txt').status_code==404
