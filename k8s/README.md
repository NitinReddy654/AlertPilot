# Kubernetes Deployment

Apply the manifests with `kubectl apply -f k8s/` to deploy the AlertPilot API, Redis, Kafka, Postgres service definitions, and the API ClusterIP service. The API deployment uses two replicas, resource requests/limits, `/health` liveness probes, and `/ready` readiness probes.

Create required secrets before applying the manifests:

```bash
kubectl create secret generic alertpilot-secrets \
  --from-literal=token-secret="replace-with-a-long-random-secret" \
  --from-literal=bootstrap-password="replace-with-a-strong-password" \
  --from-literal=postgres-password="replace-with-a-strong-password"
kubectl apply -f k8s/
```
