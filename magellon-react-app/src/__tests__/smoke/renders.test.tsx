/**
 * Render smoke tests — verify key components mount without crashing.
 * These catch runtime errors from broken component trees after refactoring.
 */
import React from 'react'
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from 'react-query'
import { ThemeProvider } from '../../app/providers/theme/index.ts'
import { AuthProvider } from '../../features/auth/model/AuthContext.tsx'

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          {ui}
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}

describe('Provider stack renders', () => {
  it('renders with all providers without crashing', () => {
    const { container } = renderWithProviders(<div data-testid="child">OK</div>)
    expect(container.textContent).toContain('OK')
  })
})

describe('Zustand stores work', () => {
  it('imageViewerStore has correct initial state', async () => {
    const { useImageViewerStore } = await import(
      '../../features/image-viewer/model/imageViewerStore.ts'
    )
    const state = useImageViewerStore.getState()
    expect(state).toBeDefined()
    expect(state).toHaveProperty('imageColumns')
    expect(state).toHaveProperty('viewMode')
  })
})
