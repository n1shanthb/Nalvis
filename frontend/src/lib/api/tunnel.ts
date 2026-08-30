/** Cloudflare quick-tunnel control plane (`/api/tunnel*`). */

export type TunnelUrls = {
  github: string
  jira: string
  gmail: string
}

export type TunnelStatus = {
  status: string
  running: boolean
  binary: boolean
  public_base: string
  local_url: string
  urls: TunnelUrls
  url_changed: boolean
  error: string
  install_hint: string | null
}

async function tunnelRequest(path: string, method: 'GET' | 'POST' = 'GET'): Promise<TunnelStatus> {
  const res = await fetch(`/api/tunnel${path}`, {
    method,
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(`Tunnel ${method} ${path || '/'} failed (${res.status})`)
  }
  return (await res.json()) as TunnelStatus
}

export function fetchTunnelStatus(): Promise<TunnelStatus> {
  return tunnelRequest('')
}

export function startTunnel(): Promise<TunnelStatus> {
  return tunnelRequest('/start', 'POST')
}

export function stopTunnel(): Promise<TunnelStatus> {
  return tunnelRequest('/stop', 'POST')
}
