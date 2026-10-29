# Invoice System - Agile DevOps Assignment

This repository provides three progressive Invoice System releases.

| Version | Capability |
| --- | --- |
| V1 | Create invoices from customer and item details; calculate, save, and display totals. |
| V2 | All V1 features plus saved-invoice history and editing. |
| V3 | All V2 features plus a dedicated, itemised invoice details page. |

## Behaviour and routes

The dependency-free Python app writes invoice data atomically to `DATA_FILE`: `data/invoices.json` locally and `/data/invoices.json` in a container. Mount `/data` to retain invoices across container replacement.

- `GET /` - current release UI
- `GET /health` - health/readiness endpoint
- `POST /api/invoices` - create
- `GET /api/invoices` - list
- `PUT /api/invoices/INV-1001` - edit (V2/V3 only)
- `GET /v3/invoices/INV-1001` - dedicated details page (V3 only)

## Local test

Use Python 3.10+:

```powershell
$env:APP_VERSION = 'v3'
$env:APP_PORT = '8080'
python -m unittest discover -s tests -v
python app.py
```

## Docker

Verify Docker Desktop is running first:

```powershell
docker version
```

Run tests and create the three distinct version-configured image tags:

```powershell
docker build --target test --tag invoice-system:test .
docker build --build-arg APP_VERSION=v1 -t sanguptha/invoice-system:v1 .
docker build --build-arg APP_VERSION=v2 -t sanguptha/invoice-system:v2 .
docker build --build-arg APP_VERSION=v3 -t sanguptha/invoice-system:v3 .
docker image ls sanguptha/invoice-system
```

Run the images separately:

```powershell
docker run -d --rm --name invoice-v1 -p 30081:8080 -v ${PWD}/data/v1:/data sanguptha/invoice-system:v1
docker run -d --rm --name invoice-v2 -p 30082:8080 -v ${PWD}/data/v2:/data sanguptha/invoice-system:v2
docker run -d --rm --name invoice-v3 -p 30083:8080 -v ${PWD}/data/v3:/data sanguptha/invoice-system:v3
```

- V1: `http://localhost:30081/`
- V2: `http://localhost:30082/`
- V3: `http://localhost:30083/`

After each container works, authenticate and push:

```powershell
docker login -u sanguptha
docker push sanguptha/invoice-system:v1
docker push sanguptha/invoice-system:v2
docker push sanguptha/invoice-system:v3
```

## Kubernetes

| Version | Deployment | Service | NodePort |
| --- | --- | --- | --- |
| V1 | `invoice-v1` | `invoice-v1-service` | 30081 |
| V2 | `invoice-v2` | `invoice-v2-service` | 30082 |
| V3 | `invoice-v3` | `invoice-v3-service` | 30083 |

After Docker Desktop Kubernetes is enabled and images are pushed:

```powershell
kubectl config current-context
kubectl apply -f k8s/invoice-v1.yaml
kubectl apply -f k8s/invoice-v2.yaml
kubectl apply -f k8s/invoice-v3.yaml
kubectl rollout status deployment/invoice-v1 --timeout=180s
kubectl rollout status deployment/invoice-v2 --timeout=180s
kubectl rollout status deployment/invoice-v3 --timeout=180s
kubectl get deployments,pods,services -l app=invoice-system -o wide
```

On Docker Desktop Kubernetes, browse the same `localhost:30081`, `30082`, and `30083` URLs after Pods are `1/1 Running`.

## Jenkins on Windows

The Jenkinsfile uses Windows `bat` and PowerShell, and requires `docker`/`kubectl` on the Jenkins agent `PATH`. It reads `C:\Users\sanph\.kube\config`. Configure a Jenkins **Username with password** credential with Docker Hub username/token, enter its ID in `DOCKERHUB_CREDENTIALS_ID`, then select `PUSH_IMAGES`. Select `DEPLOY_TO_KUBERNETES` only after the Jenkins agent has a working Kubernetes context.

## Evidence checklist

1. Capture V1 create, V2 list/edit, and V3 details in the three URLs above.
2. Capture `docker image ls sanguptha/invoice-system` (or Docker Desktop **Images**) showing `v1`, `v2`, and `v3`.
3. Capture `kubectl get deployments,pods,services -l app=invoice-system -o wide` or Docker Desktop **Kubernetes > default**, with three ready Deployments and Pods.
4. Capture the GitHub repository root showing `app.py`, `Dockerfile`, `Jenkinsfile`, `k8s/`, `tests/`, and this README after a verified push.
