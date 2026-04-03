# Remote Access

The Web UI can be exposed beyond your LAN using Cloudflare Tunnels or accessed directly by other devices on the same network.

## LAN Access

By default the server binds to `0.0.0.0`, making it accessible to any device on your local network at `http://<your-ip>:3000`. The mode indicator in the System tab reads **LAN Only**.

## Cloudflare Tunnel

Saturn can start a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to expose the Web UI over the internet with a public HTTPS URL.

!!! note
    `cloudflared` must be installed and available in your PATH. Install it from [Cloudflare's releases](https://github.com/cloudflare/cloudflared/releases).

### Starting a Tunnel

Open the Remote subtab under System and click **Start Tunnel**. An access warning overlay appears first — you must confirm before the tunnel activates.

Once running, the panel shows:

- **Status** — `Tunnel Active` with a green indicator
- **URL** — the public `https://*.trycloudflare.com` URL
- **QR code** — scannable link for mobile devices

### Stopping a Tunnel

Click **Stop Tunnel**. The mode indicator returns to **LAN Only** and the public URL is immediately invalidated.

### LAN Fallback

If the tunnel process crashes or `cloudflared` is not found, the UI falls back to LAN-only mode and displays an error in the Remote panel. All local access continues to work normally.

!!! warning
    Enabling a tunnel exposes your Saturn instance to the public internet. Anyone with the URL can access the chat interface. Use this for temporary sharing, not permanent deployment.
