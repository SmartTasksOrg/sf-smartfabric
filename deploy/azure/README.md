# Azure deploy

```
az vm create -g <rg> -n smartfabric-node \
  --image Ubuntu2204 --size Standard_B1s \
  --custom-data cloud-init.yaml --generate-ssh-keys
az vm open-port -g <rg> -n smartfabric-node --port 8770
```

Verify: `sf-smartfabric live --url http://<public-ip>:8770`.

Production: front with Application Gateway + TLS, restrict the NSG source, and add
the registry/mTLS fabric services (docs/04). Same container image as the Dockerfile.
