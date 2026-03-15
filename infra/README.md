# Infrastructure Notes

This repository is intentionally minimal on infrastructure, but now includes practical Cloud Build pipelines for provisioning and backend deploy.

## Deployment direction

- Backend: Google Cloud Run
- Frontend: Firebase Hosting
- Model access: Gemini Live API and Vertex AI
- Secrets: Secret Manager
- Future persistence: likely Cloud SQL or Firestore, depending on session-state needs

## Cloud Build pipelines

- `cloudbuild/provision.yaml`: idempotent setup for APIs, Artifact Registry, runtime service account, and secret access
- `cloudbuild/deploy-backend.yaml`: docker build/push and Cloud Run deploy for `backend/Dockerfile`
- `cloudbuild/deploy-frontend.yaml`: Vite build and Firebase Hosting deploy for `frontend/`

See [Cloud Build Provisioning](/Users/alanmaizon/vista/infra/cloudbuild.md) for commands, IAM prerequisites, and recommended trigger setup.
