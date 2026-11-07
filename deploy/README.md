# Free-allowance hosting with Modal

Status: deployment prepared locally; no public deployment has been created.

Modal Starter offers $30/month in free compute credits. It requires a payment
method. Free credits are a usage allowance, not unlimited hosting. Use only
Starter, CPU compute, and a **workspace spend limit of $0** (net charges after
credits). Do not confuse this with the gross usage budget. When credits run out,
the app may stop serving requests. Verify the account's current pricing and
billing settings before deploying:

- https://modal.com/pricing
- https://modal.com/docs/guide/budgets
- https://modal.com/docs/guide/billing

## Required account step

1. Create/sign in to a Modal Starter account at https://modal.com.
2. In Settings > Usage & Billing, set the workspace spend limit to **$0** and
   confirm it is saved. Do not enable a paid subscription or raise that limit.
3. Authenticate locally using the commands below. Never paste tokens into chat,
   commit them, or put them in deployment source files.

```powershell
.venv/Scripts/python.exe -m pip install modal
.venv/Scripts/python.exe -m modal token new
```

## Deploy

The existing local restoration and metric assets must already be provisioned
using scripts/setup_model.py and scripts/setup_iqa.py. They are copied into the
cloud image; no datasets, local .env, or saved user images are included.

After verifying the zero-dollar spend limit:

```powershell
$env:LUMA_ZERO_SPEND_CONFIRMED = '1'
.venv/Scripts/python.exe -m modal deploy deploy/modal_app.py
```

The command prints the actual HTTPS URL. Verify `/health`, `/api/models`, an
enhancement request, and a batch job before sharing it. Check CPU-memory use and
remaining credits in the dashboard. Deployment code has been syntax-checked;
the cloud build and live endpoints require account authentication and have not
yet been verified.

The frontend and backend share one origin. A single CPU container scales to
zero when idle, so cold starts are expected. Processing is capped at 1024px,
uploads at 10 MB, and batches at eight images. Full-resolution research runs
remain available locally. Saved outputs use a Modal volume and count toward
the account's usage. Single-container concurrency prevents cross-instance job
routing; restart/interruption can still interrupt running jobs. This is not an
unlimited, always-on service guarantee.

Stop hosting when no longer needed:

```powershell
.venv/Scripts/python.exe -m modal app stop lumarestore
```

Stopping the app does not remove the results volume. Delete that volume through
the dashboard only after exporting any results you need.
