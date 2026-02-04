# Umami Analytics Deployment

Self-hosted, privacy-focused analytics for kcirtap.io.

## Prerequisites

- Kubernetes cluster with ArgoCD
- Cloudflare Tunnel (already configured in `k8s/cloudflare-tunnel.yaml`)

## Setup Steps

### 1. Create Sealed Secret

Generate and seal the secrets:

```bash
# Generate secrets
APP_SECRET=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 24)

# Create temp secret file
cat <<EOF > /tmp/umami-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: umami-secrets
  namespace: umami
type: Opaque
stringData:
  APP_SECRET: "${APP_SECRET}"
  POSTGRES_USER: "umami"
  POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
  POSTGRES_DB: "umami"
  DATABASE_URL: "postgresql://umami:${POSTGRES_PASSWORD}@umami-postgres:5432/umami"
EOF

# Seal it
kubeseal --format yaml < /tmp/umami-secret.yaml > k8s/umami/sealed-secret.yaml

# Clean up
rm /tmp/umami-secret.yaml
```

Commit the `sealed-secret.yaml` file.

### 2. Cloudflare Tunnel

The route for `umami.kcirtap.io` has been added to `k8s/cloudflare-tunnel.yaml`.

If you're using a Helm chart for cloudflared, add this to your ingress rules:
```yaml
- hostname: umami.kcirtap.io
  service: http://umami.umami.svc.cluster.local:80
```

### 3. Deploy with ArgoCD

The ArgoCD Application is defined in `_think_talos_k8s/argo/apps/umami.yaml`.

If using App of Apps, it will sync automatically. Otherwise, apply manually:

```bash
kubectl apply -f _think_talos_k8s/argo/apps/umami.yaml
```

Or deploy directly without ArgoCD:

```bash
kubectl apply -k k8s/umami/
```

### 4. Initial Login

1. Access `https://umami.kcirtap.io`
2. Login with default credentials:
   - Username: `admin`
   - Password: `umami`
3. **Immediately change the admin password!**

### 5. Add Your Website

1. Go to Settings > Websites > Add website
2. Enter:
   - Name: `kcirtap.io`
   - Domain: `kcirtap.io`
3. Copy the generated **Website ID**
4. Update `templates/base.html` with your Website ID:

```html
<script defer src="https://umami.kcirtap.io/script.js" data-website-id="YOUR_WEBSITE_ID"></script>
```

## Resource Usage

- **Umami**: ~128-512MB RAM, minimal CPU
- **PostgreSQL**: ~128-512MB RAM, 5GB storage

## Troubleshooting

Check pod status:
```bash
kubectl get pods -n umami
kubectl logs -n umami deployment/umami
kubectl logs -n umami deployment/umami-postgres
```

Check database connection:
```bash
kubectl exec -n umami deployment/umami -- env | grep DATABASE
```
