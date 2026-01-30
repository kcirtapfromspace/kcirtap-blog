#!/bin/bash
set -e

# Configuration
IMAGE_NAME="kcirtap-site"
IMAGE_TAG="${1:-latest}"

echo "==> Building site with Zola..."
zola build

echo "==> Building Docker image..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "==> Loading image to local cluster..."
# For minikube:
if command -v minikube &> /dev/null && minikube status &> /dev/null; then
    echo "Detected minikube - loading image..."
    minikube image load "${IMAGE_NAME}:${IMAGE_TAG}"
fi

# For kind:
if command -v kind &> /dev/null && kind get clusters 2>/dev/null | grep -q .; then
    echo "Detected kind - loading image..."
    kind load docker-image "${IMAGE_NAME}:${IMAGE_TAG}"
fi

# For k3d:
if command -v k3d &> /dev/null && k3d cluster list 2>/dev/null | grep -q .; then
    echo "Detected k3d - loading image..."
    k3d image import "${IMAGE_NAME}:${IMAGE_TAG}"
fi

# For Docker Desktop Kubernetes or Rancher Desktop - image is already available

echo "==> Deploying to Kubernetes..."
kubectl apply -k k8s/

echo "==> Waiting for deployment..."
kubectl rollout status deployment/kcirtap-site -n kcirtap --timeout=120s

echo "==> Deployment complete!"
echo ""
echo "Access options:"
echo "  1. Port forward: kubectl port-forward -n kcirtap svc/kcirtap-site 8080:80"
echo "     Then visit: http://localhost:8080"
echo ""
echo "  2. Add to /etc/hosts: 127.0.0.1 kcirtap.local"
echo "     Then visit: http://kcirtap.local (requires ingress controller)"
echo ""
echo "  3. NodePort (if using minikube): minikube service kcirtap-site -n kcirtap"
