# Infrastructure Notes

This repository is intentionally light on infrastructure for now.

## Deployment direction

- Backend: Google Cloud Run
- Model access: Gemini Live API and Vertex AI
- Secrets: Secret Manager
- Future persistence: likely Cloud SQL or Firestore, depending on session-state needs

## Why there is no deployment automation yet

The app surface is still scaffold-level, so shipping Terraform or Cloud Build config right now would create fake completeness. The backend Dockerfile is present because it is a low-cost, useful foundation for later Cloud Run deployment.

