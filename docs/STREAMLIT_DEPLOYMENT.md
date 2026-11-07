# Deploy LumaRestore on Streamlit Community Cloud

This is a separate Python demo interface. The existing React/FastAPI app,
Docker image, research metrics, and CLI workflows remain available.

## Local check (Python 3.11)

```powershell
python -m venv .venv-streamlit
.venv-streamlit/Scripts/python.exe -m pip install -r requirements.txt
.venv-streamlit/Scripts/python.exe -m streamlit run streamlit_app.py
```

Use a separate environment from the full desktop application: the demo installs
headless OpenCV and CPU-only PyTorch, without the large IQA dependency tree.

## Free hosting

1. Visit https://share.streamlit.io and sign in with GitHub.
2. Choose **Create app** and deploy from an existing GitHub repository.
3. Select `Tanish3115/Robust-Low-Light-Image-Restoration-and-Enhancement`.
4. Select branch `main` and entry point `streamlit_app.py`.
5. In advanced settings, select Python **3.11**.
6. Choose an available subdomain, then click **Deploy**.
7. Check deployment logs, upload an image, test Classical first, then Deep and
   Hybrid at 256 or 384 pixels, and verify the PNG/report downloads.

No API keys, paid inference service, Node build, or external backend is required.
Do not enter payment information or start a paid Snowflake service for this demo.
The public URL is assigned by Streamlit; no URL is claimed until deployment
succeeds under your account. Subsequent commits can redeploy the app.

## Resource limits and model behaviour

- Processing defaults to 512px; available edges range from 256 to 768px.
- Uploads are limited to 10 MB and 20 million decoded pixels.
- A shared gate permits only one processing request at a time across visitors.
- Model weights are downloaded on first neural use from the official linked
  source, checked against the verified LOL-v1 SHA256, and loaded strictly.
  The model is cached across sessions. Local image results stay in the session,
  without building an on-disk user-image archive.
- Auto mode explicitly reports any classical fallback if neural loading fails.
  Explicit Deep/Hybrid failures are errors, never substituted neural results.
- PSNR/SSIM require an aligned, dimension-matched reference. LPIPS/NIQE are
  explicitly unavailable in this lightweight deployment. The full app retains
  them, batch evaluation, all ablations, and optional 4K export.
- Free cloud memory, CPU and concurrent-user limits still apply. Neural modes
  require live verification; CPU support does not guarantee resource availability.
  Reduce processing size or use Classical if the cloud instance cannot sustain
  neural inference.
- Community Cloud apps sleep after inactivity; wake-up/model download time
  varies. This is a demo deployment, not an always-on service guarantee.

Official instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud
