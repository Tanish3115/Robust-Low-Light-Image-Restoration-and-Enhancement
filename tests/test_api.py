def test_health_and_models(client):
    assert client.get('/health').json()['status']=='ok'
    models=client.get('/api/models').json()['models']
    assert models['classical']['available']
    assert not models['deep']['available']
    assert not models['hybrid']['available']


def test_complete_classical_upload_download_flow(client,png):
    response=client.post('/api/enhance',files={'file':('dark.png',png,'image/png')},data={'mode':'classical'})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['executed_mode']=='classical'
    assert result['latency_ms']>0
    assert not result['metrics']['psnr']['available']
    image=client.get(result['artifacts']['enhanced'])
    assert image.status_code==200 and image.content.startswith(b'\x89PNG')
    assert client.get('/api/results/'+result['id']).json()['id']==result['id']
    csv=client.get(f"/api/results/{result['id']}/metrics")
    assert csv.status_code==200 and 'latency_ms' in csv.text
    assert client.get(f"/api/results/{result['id']}/report").status_code==200


def test_comparison_reference_and_missing_neural(client,png):
    response=client.post('/api/compare',files={'file':('input.png',png),'reference':('ref.png',png)})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['comparisons']['classical']['metrics']['ssim']['available']
    assert result['comparisons']['deep']['unavailable']
    assert result['comparisons']['hybrid']['unavailable']


def test_invalid_mode_and_missing_checkpoint(client,png):
    assert client.post('/api/enhance',files={'file':('x.png',png)},data={'mode':'bogus'}).status_code==422
    for mode in ('deep','hybrid'):
        response=client.post('/api/enhance',files={'file':('x.png',png)},data={'mode':mode})
        assert response.status_code==503
        assert 'checkpoint' in response.json()['detail'].lower()
    result=client.post('/api/enhance',files={'file':('x.png',png)},data={'mode':'auto'}).json()
    assert result['executed_mode']=='classical'


def test_bad_upload_and_unknown_results(client):
    assert client.post('/api/analyze',files={'file':('x.png',b'not an image')}).status_code==422
    assert client.get('/api/results/not-a-uuid').status_code==404
    assert client.get('/api/results/'+'0'*32+'/arbitrary').status_code==404


def test_analysis_and_evaluation(client,png):
    analyzed=client.post('/api/analyze',files={'file':('x.png',png)}).json()
    assert 'edge_map' in analyzed['artifacts']
    assert analyzed['executed_mode']=='analysis'
    evaluated=client.post('/api/evaluate',files={'file':('x.png',png)},data={'mode':'classical'})
    assert evaluated.status_code==200
    assert evaluated.json()['metrics']['ssim']['value'] is None


def test_busy_engine_is_bounded(client,png):
    import backend.app.main as module
    assert module.service.gate.acquire(blocking=False)
    try:
        response=client.post('/api/enhance',files={'file':('x.png',png)})
        assert response.status_code==429
    finally:module.service.gate.release()


def test_oversized_upload_and_reference_mismatch(client,png):
    import io
    from PIL import Image
    import backend.app.main as module
    module.settings.max_upload_mb=1
    response=client.post('/api/enhance',files={'file':('huge.png',b'x'*(1024**2+1))})
    assert response.status_code==413
    ref=io.BytesIO();Image.new('RGB',(20,20)).save(ref,format='PNG')
    response=client.post('/api/compare',files={'file':('x.png',png),'reference':('wrong.png',ref.getvalue())})
    assert response.status_code==422
    assert 'dimensions' in response.json()['detail']
