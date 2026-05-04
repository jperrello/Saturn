# Cloudflare Tunnels

Saturn supports Cloudflare tunnels for remote access to your local Saturn instance. This lets users outside your network reach Saturn without port forwarding or a static IP.

## Prerequisites

Install `cloudflared` on the machine running Saturn:

```bash
# macOS
brew install cloudflared

# Linux
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

No Cloudflare account or configuration is needed. Saturn uses Cloudflare's quick tunnels (TryCloudflare), which generate a temporary public URL.

## Starting a tunnel

### Via Web UI

Navigate to **System > Remote** in the Web UI. Click the tunnel start button. Saturn starts `cloudflared` and displays the public URL once it's ready.

### Via API

```bash
curl -X POST http://localhost:3000/api/brutus/tunnel/start \
  -H "Authorization: Bearer $SATURN_ADMIN_TOKEN"
```

Saturn launches `cloudflared`, then polls for up to 30 seconds waiting for the tunnel URL and DNS propagation. The response includes the public URL:

```json
{
  "url": "https://random-words.trycloudflare.com",
  "status": "active"
}
```

## Sharing access

Once the tunnel is active, a QR code is generated for easy sharing. The QR code encodes the tunnel URL and can be scanned by mobile devices.

In the Web UI, the QR code appears automatically in the System > Remote tab. Via API:

```bash
curl http://localhost:3000/api/brutus/tunnel/status \
  -H "Authorization: Bearer $SATURN_ADMIN_TOKEN"
```

## Stopping a tunnel

### Via Web UI

Click the tunnel stop button in **System > Remote**.

### Via API

```bash
curl -X POST http://localhost:3000/api/brutus/tunnel/stop \
  -H "Authorization: Bearer $SATURN_ADMIN_TOKEN"
```

## Notes

- Tunnel URLs are temporary and change each time a tunnel is started.
- The 30-second startup timeout accounts for DNS propagation. If the tunnel fails to start in time, retry.
- All traffic through the tunnel is encrypted via Cloudflare's network.
- The tunnel exposes only the Saturn Web UI port, not the entire machine.

!!! warning
    Anyone with the tunnel URL can reach your Saturn instance. Admin endpoints (`/api/*`, including the tunnel start/stop calls above) require `SATURN_ADMIN_TOKEN` as a Bearer header; the chat interface is open by default. Set both `SATURN_ADMIN_PASSWORD` (for the Web-UI login) and `SATURN_ADMIN_TOKEN` (for the API) before starting a tunnel — neither has a default per CONFIG_FIELDS §A.2, and Saturn refuses to start without them.
