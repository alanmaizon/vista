# Cloud Build Provisioning

This repo now includes two Cloud Build pipelines:

- `cloudbuild/provision.yaml`: idempotent project setup (APIs, Artifact Registry repo, runtime service account, and secret wiring)
- `cloudbuild/deploy-backend.yaml`: backend image build/push + Cloud Run deploy
- `cloudbuild/deploy-frontend.yaml`: frontend build + Firebase Hosting deploy

In this project today, Cloud Build jobs are running as `PROJECT_NUMBER-compute@developer.gserviceaccount.com`.

## 1) Grant Cloud Build provisioning IAM

Use the build service account from your project:

```bash
PROJECT_ID="vista-ai-488623"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# If your project uses the legacy Cloud Build SA, use:
# BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
```

Grant roles needed by `cloudbuild/provision.yaml`:

```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/serviceusage.serviceUsageAdmin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/iam.serviceAccountAdmin"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/secretmanager.admin"
```

## 2) Grant Cloud Build deploy IAM

Grant roles needed by `cloudbuild/deploy-backend.yaml`:

```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding \
  "tutor-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"
```

## 3) Grant Firebase Hosting deploy IAM

The frontend pipeline uses the existing Firebase Admin service-account JSON secret:
`vista-firebase-adminsdk`.

Give your build service account permission to read it:

```bash
gcloud secrets add-iam-policy-binding "vista-firebase-adminsdk" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## 4) Run provisioning pipeline

```bash
gcloud builds submit \
  --project="vista-ai-488623" \
  --config="cloudbuild/provision.yaml" \
  --substitutions="_REGION=us-central1,_AR_REPO=ancient-greek-backend,_RUNTIME_SA=tutor-runtime" \
  .
```

## 5) Seed the Gemini secret value

```bash
printf '%s' "YOUR_GEMINI_API_KEY" | \
gcloud secrets versions add TUTOR_GEMINI_API_KEY \
  --project="vista-ai-488623" \
  --data-file=-
```

## 6) Run backend deploy pipeline

```bash
gcloud builds submit \
  --project="vista-ai-488623" \
  --config="cloudbuild/deploy-backend.yaml" \
  --substitutions="_REGION=us-central1,_SERVICE_NAME=vista-ai-backend,_AR_REPO=ancient-greek-backend,_RUNTIME_SA=tutor-runtime,_ALLOW_UNAUTHENTICATED=true,_TUTOR_USE_GOOGLE_ADK=true,_CORS_ORIGINS=https://vista-ai-488623.web.app;https://vista-ai-488623.firebaseapp.com" \
  .
```

`_CORS_ORIGINS` accepts comma or semicolon delimiters. Semicolons are easier with `gcloud builds submit --substitutions` because that flag uses commas between key/value pairs.

## 7) Run frontend deploy pipeline

```bash
gcloud builds submit \
  --project="vista-ai-488623" \
  --config="cloudbuild/deploy-frontend.yaml" \
  --substitutions="_FRONTEND_DIR=frontend,_API_BASE_URL=https://vista-ai-backend-en2ftwmt7q-uc.a.run.app,_FIREBASE_PROJECT_ID=vista-ai-488623" \
  .
```

Default Firebase Hosting URLs:

- `https://vista-ai-488623.web.app`
- `https://vista-ai-488623.firebaseapp.com`

## 8) Optional trigger setup

You can create three triggers on `main`:

- `provision-infra` -> `cloudbuild/provision.yaml` (manual trigger is often safer)
- `deploy-backend` -> `cloudbuild/deploy-backend.yaml`
- `deploy-frontend` -> `cloudbuild/deploy-frontend.yaml`

Recommended: keep provisioning manual, and auto-trigger deploy only after provisioning has already succeeded once.
