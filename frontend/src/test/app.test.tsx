import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import App from '@/App'
import { getDemoAdapter } from '@/lib/api'
import { useDemoStore } from '@/lib/store'
import { ContextStudioPage } from '@/pages/ContextStudioPage'
import { IntegrationsPage } from '@/pages/IntegrationsPage'
import { AppShell } from '@/components/layout/AppShell'

async function hydrateStore() {
  getDemoAdapter().reset()
  await useDemoStore.getState().hydrate()
}

function renderAt(ui: ReactNode, path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="*" element={ui} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('empty console honesty', () => {
  beforeEach(async () => {
    vi.unstubAllGlobals()
    await hydrateStore()
  })

  it('starts with no projects and no synthetic badge', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument()
    expect(screen.getByText('No projects yet')).toBeInTheDocument()
    expect(screen.getByText('No synthetic data')).toBeInTheDocument()
    expect(useDemoStore.getState().agents).toHaveLength(0)
    expect(useDemoStore.getState().runs).toHaveLength(0)
    expect(useDemoStore.getState().approvals).toHaveLength(0)
  })

  it('loads live integration health from the API', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => {
      if (String(url).includes('/api/tunnel')) {
        return {
          ok: true,
          json: async () => ({
            status: 'stopped',
            running: false,
            binary: true,
            public_base: '',
            local_url: 'http://127.0.0.1:8000',
            urls: { github: '', jira: '', gmail: '' },
            url_changed: false,
            error: '',
            install_hint: null,
          }),
        }
      }
      return {
        ok: true,
        json: async () => ({
          ok: false,
          checked_at: '2026-08-29T12:00:00+00:00',
          integrations: [
            {
              name: 'github',
              displayName: 'GitHub (MCP + App)',
              status: 'healthy',
              credentialsConfigured: true,
              lastSuccessfulCallAt: null,
              lastError: null,
              rateLimitRemaining: null,
              rateLimitResetAt: null,
              latencyMsP50: null,
              transport: 'mcp+app',
              config: { mcp_enabled: true, smoke_repo: 'analytics-resume' },
            },
            {
              name: 'jira',
              displayName: 'Jira (Atlassian MCP)',
              status: 'down',
              credentialsConfigured: false,
              lastSuccessfulCallAt: null,
              lastError: 'ATLASSIAN_MCP_TOKEN missing',
              rateLimitRemaining: null,
              rateLimitResetAt: null,
              latencyMsP50: null,
              transport: 'mcp',
              config: { mcp_enabled: true },
            },
            {
              name: 'gmail',
              displayName: 'Gmail (native OAuth)',
              status: 'healthy',
              credentialsConfigured: true,
              lastSuccessfulCallAt: null,
              lastError: null,
              rateLimitRemaining: null,
              rateLimitResetAt: null,
              latencyMsP50: null,
              transport: 'native',
              config: { enabled: true, user: 'ops@example.com' },
            },
            {
              name: 'calendar',
              displayName: 'Calendar (native OAuth)',
              status: 'healthy',
              credentialsConfigured: true,
              lastSuccessfulCallAt: null,
              lastError: null,
              rateLimitRemaining: null,
              rateLimitResetAt: null,
              latencyMsP50: null,
              transport: 'native',
              config: { shares_gmail_oauth: true },
            },
          ],
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    renderAt(<IntegrationsPage />, '/integrations')
    expect(screen.getByRole('heading', { name: 'Integrations Health' })).toBeInTheDocument()
    expect(await screen.findByText('GitHub (MCP + App)')).toBeInTheDocument()
    expect(screen.getByText('Jira (Atlassian MCP)')).toBeInTheDocument()
    expect(screen.getByText('Gmail (native OAuth)')).toBeInTheDocument()
    expect(screen.getByText('Calendar (native OAuth)')).toBeInTheDocument()
    expect(screen.getByText('ATLASSIAN_MCP_TOKEN missing')).toBeInTheDocument()
    expect(screen.getByText('smoke repo')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Inbound webhook tunnel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start tunnel' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/integrations/health',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    )
  })

  it('shows control-plane error when integrations health fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => {
        if (String(url).includes('/api/tunnel')) {
          return {
            ok: true,
            json: async () => ({
              status: 'stopped',
              running: false,
              binary: true,
              public_base: '',
              local_url: 'http://127.0.0.1:8000',
              urls: { github: '', jira: '', gmail: '' },
              url_changed: false,
              error: '',
              install_hint: null,
            }),
          }
        }
        return { ok: false, status: 502 }
      }),
    )
    renderAt(<IntegrationsPage />, '/integrations')
    expect(await screen.findByText('Could not reach control plane')).toBeInTheDocument()
  })

  it('parses only operator-provided paste (no preload)', async () => {
    const user = userEvent.setup()
    renderAt(<ContextStudioPage />, '/context')
    const box = screen.getByRole('textbox', { name: 'Company context input' })
    expect(box).toHaveValue('')

    await user.click(box)
    await user.paste(
      '{"company":"Acme","products":[{"name":"Payments","repos":["acme/pay"]}]}',
    )
    await user.click(screen.getByRole('button', { name: 'Parse paste' }))
    await waitFor(() => {
      expect(screen.getByText('Payments')).toBeInTheDocument()
    })
    expect(useDemoStore.getState().contextDocuments[0]?.parsePreview?.products).toEqual([
      'Payments',
    ])
    // Workspaces remain empty until control plane creates them
    expect(useDemoStore.getState().workspaces).toHaveLength(0)
  })
})
