"""Free Community Cloud demo. Run: streamlit run streamlit_app.py"""
import hashlib
import json

import streamlit as st

from backend.app.streamlit_runtime import DemoRuntime

st.set_page_config(page_title='LumaRestore AI', page_icon='🌅', layout='wide')


@st.cache_resource
def runtime():
    return DemoRuntime()


def main():
    st.title('LumaRestore AI')
    st.write('Brighten low-light images with classical enhancement, pretrained Retinexformer, or adaptive hybrid restoration.')
    st.caption('Free CPU demo. Neural modes download verified weights on first use; cold starts can take time.')
    with st.sidebar:
        st.header('Enhancement settings')
        mode = st.selectbox('Mode', ['auto', 'classical', 'deep', 'hybrid'])
        side = st.select_slider('Maximum processing edge', options=[256, 384, 512, 768], value=512)
        strength = st.slider('Classical strength', .3, 1.5, 1., .05, disabled=mode == 'deep')
        vivid = st.checkbox('Vivid finish', value=True, help='Brighter midtones, richer colours and subtle sharpening.')
        st.info('Try 256 or 384 pixels if neural processing is slow. Only one image is processed at a time across visitors.')
        st.caption('This demo uses the same restoration modules as the full app. Batch research tools and LPIPS/NIQE remain in the desktop/Docker version.')
    upload = st.file_uploader('Upload a low-light image', type=['png', 'jpg', 'jpeg', 'webp'])
    reference = st.file_uploader('Aligned reference image (optional, for PSNR/SSIM)', type=['png', 'jpg', 'jpeg', 'webp'])
    if upload is None:
        st.session_state.pop('restoration', None)
        st.info('Upload a JPEG, PNG or WebP image up to 10 MB to begin.')
        return
    data = upload.getvalue()
    ref_data = reference.getvalue() if reference else None
    signature = (hashlib.sha256(data).hexdigest(), hashlib.sha256(ref_data).hexdigest() if ref_data else None,
                 mode, side, strength, vivid)
    if st.button('Enhance image', type='primary'):
        st.session_state.pop('restoration', None)
        try:
            with st.spinner('Restoring your image. First neural use also downloads and loads the model...'):
                result = runtime().run(data, mode=mode, max_side=side, strength=strength, vivid=vivid, reference_data=ref_data)
            st.session_state.restoration = (signature, result)
        except Exception as exc:
            st.error(str(exc))
            st.caption('You can retry with Classical mode and a smaller processing edge.')
    saved = st.session_state.get('restoration')
    if not saved or saved[0] != signature:
        st.caption('Click Enhance image to process the current image and settings.')
        return
    result = saved[1]
    left, right = st.columns(2)
    left.image(result['original_png'], caption='Original (processing size)', use_container_width=True)
    right.image(result['enhanced_png'], caption='Enhanced', use_container_width=True)
    report = result['report']
    st.success(f"Executed: {report['executed_mode']}" + (' + Vivid finish' if vivid else ''))
    st.download_button('Download enhanced PNG', result['enhanced_png'], 'lumarestore-enhanced.png', 'image/png')
    st.download_button('Download measured report', json.dumps(report, indent=2, allow_nan=False),
                       'lumarestore-report.json', 'application/json')
    for notice in report['notices']:
        st.warning(notice)
    st.subheader('Measured indicators')
    st.table([{'Metric': name.upper(), 'Value': 'Infinity' if item.get('infinite') else str(item['value']) if item['available'] else 'Unavailable',
               'Better': item['direction'], 'Note': item.get('reason') or ''}
              for name, item in report['metrics'].items()])
    with st.expander('Analysis, controller and quality diagnostics'):
        st.json(report)
    st.caption('Metrics describe this processed image, not a dataset benchmark. Enlarging images cannot reconstruct missing detail.')


if __name__ == '__main__':
    main()
