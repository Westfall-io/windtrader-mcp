# windtrader-mcp Helm chart

Deploys `windtrader-mcp` (the SysMLv2 validator MCP server) with the
**Streamable HTTP** transport so multiple MCP clients can share one instance.

## Quick start

```bash
helm repo add westfall https://<chart-repo>  # or use the local chart dir
helm upgrade --install windtrader-mcp ./deploy/charts/windtrader-mcp \
  --namespace windtrader --create-namespace \
  --set image.tag=0.3.0
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `ghcr.io/westfall-io/windtrader-mcp` | Image repo |
| `image.tag` | `0.3.0` | Immutable semver tag (pin releases, not `latest`) |
| `replicaCount` | `1` | Keep 1: MCP sessions are stateful (in-memory) |
| `mcp.host` | `0.0.0.0` | Bind all interfaces (required for K8s) |
| `mcp.port` | `8000` | Container port |
| `mcp.path` | `/mcp` | Streamable HTTP endpoint |
| `service.type` | `ClusterIP` | Service type |
| `service.port` | `80` | Service port → `targetPort: mcp` |
| `ingress.enabled` | `false` | Expose via Ingress |
| `resources` | 1 CPU / 1Gi limit | Sane default for JVM-backed validator |

## Notes for the cluster operator

- The image is **private** in GHCR; unless the package is made public, the
  cluster needs an imagePullSecret (set `imagePullSecrets` and create a
  docker-registry secret for `ghcr.io` with a token that can read packages).
- Endpoint inside cluster: `http://windtrader-mcp.<namespace>:80/mcp`
  (POST JSON-RPC, `text/event-stream` responses).
- Client config example:

```json
{
  "mcpServers": {
    "windtrader": {
      "url": "http://windtrader-mcp.windtrader.svc.cluster.local:80/mcp"
    }
  }
}
```

- The validator runs windtrader java jar with OpenJDK 21; the image is offline
  (jar pre-cached at build).
