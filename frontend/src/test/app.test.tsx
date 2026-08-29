import { beforeEach, describe, expect, it } from 'vitest'
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

  it('shows empty integrations honestly', async () => {
    renderAt(<IntegrationsPage />, '/integrations')
    expect(screen.getByRole('heading', { name: 'Integrations Health' })).toBeInTheDocument()
    expect(screen.getByText('No integration health data')).toBeInTheDocument()
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
