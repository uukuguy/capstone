#!/bin/sh
# Review and supply every variable before running. This file is a deployment template.
set -eu

: "${CAPSTONE_IMAGE_DIGEST:?Set the same immutable image digest for both roles}"
: "${CAPSTONE_REGION:?Set the Cloud Run region}"
: "${CAPSTONE_API_HOST:?Set the API service host or custom domain, without scheme}"
: "${CAPSTONE_APP_ORIGIN:?Set the Vercel HTTPS origin}"
: "${CAPSTONE_GCS_BUCKET:?Set the private GCS bucket name}"
: "${CAPSTONE_CLOUDSQL_INSTANCE:?Set the Cloud SQL project:region:instance}"
: "${CAPSTONE_SERVICE_ACCOUNT:?Set the API service account}"
: "${CAPSTONE_WORKER_ACCOUNT:?Set the worker service account}"

# Secret Manager entries must already contain the PostgreSQL URL and operator token.
# Give both identities database access; grant the worker object write/read and API read.
gcloud run deploy capstone-api \
  --region "$CAPSTONE_REGION" \
  --image "$CAPSTONE_IMAGE_DIGEST" \
  --args=api \
  --service-account "$CAPSTONE_SERVICE_ACCOUNT" \
  --cpu 1 --memory 1Gi \
  --add-cloudsql-instances "$CAPSTONE_CLOUDSQL_INSTANCE" \
  --allow-unauthenticated \
  --timeout 3600 \
  --set-env-vars "CAPSTONE_ALLOWED_HOSTS=$CAPSTONE_API_HOST,CAPSTONE_ALLOWED_ORIGINS=$CAPSTONE_APP_ORIGIN,CAPSTONE_ARTIFACT_BACKEND=gcs,CAPSTONE_ARTIFACT_BUCKET=$CAPSTONE_GCS_BUCKET" \
  --set-secrets 'DATABASE_URL=capstone-database-url:latest,CAPSTONE_OPERATOR_TOKEN=capstone-operator-token:latest'

gcloud run worker-pools deploy capstone-worker \
  --region "$CAPSTONE_REGION" \
  --image "$CAPSTONE_IMAGE_DIGEST" \
  --args=worker \
  --instances 1 \
  --service-account "$CAPSTONE_WORKER_ACCOUNT" \
  --cpu 2 --memory 4Gi \
  --add-cloudsql-instances "$CAPSTONE_CLOUDSQL_INSTANCE" \
  --set-env-vars "CAPSTONE_ALLOWED_HOSTS=$CAPSTONE_API_HOST,CAPSTONE_ALLOWED_ORIGINS=$CAPSTONE_APP_ORIGIN,CAPSTONE_ARTIFACT_BACKEND=gcs,CAPSTONE_ARTIFACT_BUCKET=$CAPSTONE_GCS_BUCKET" \
  --set-secrets 'DATABASE_URL=capstone-database-url:latest,CAPSTONE_OPERATOR_TOKEN=capstone-operator-token:latest'
