import { DemoAdapter } from './demo-adapter'
import { HttpAdapter } from './http-adapter'
import type { ApiAdapter } from './types'

export type AdapterMode = 'demo' | 'http'

const mode = (import.meta.env.VITE_API_MODE as AdapterMode | undefined) ?? 'demo'

let singleton: ApiAdapter | null = null

export function createAdapter(override?: AdapterMode): ApiAdapter {
  const m = override ?? mode
  if (m === 'http') return new HttpAdapter()
  return new DemoAdapter()
}

export function getAdapter(): ApiAdapter {
  singleton ??= createAdapter()
  return singleton
}

/** Used by the Zustand store so mutations stay on one DemoAdapter instance. */
export function getDemoAdapter(): DemoAdapter {
  const adapter = getAdapter()
  if (!(adapter instanceof DemoAdapter)) {
    throw new Error('Demo store requires DemoAdapter (set VITE_API_MODE=demo)')
  }
  return adapter
}

export { DemoAdapter, HttpAdapter }
export type { ApiAdapter }
