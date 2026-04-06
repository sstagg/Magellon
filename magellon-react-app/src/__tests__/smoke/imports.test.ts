/**
 * Import smoke tests — verify that key modules resolve and export expected symbols.
 * These catch broken imports immediately after file moves during FSD refactoring.
 *
 * Heavy components (pages, ImageWorkspace, ColumnBrowser) are excluded because they
 * transitively import @mui/icons-material (thousands of files) and hit Windows EMFILE
 * limits. Those are verified by `npm run build` instead.
 */
import { describe, it, expect } from 'vitest'

describe('Shared layer imports', () => {
  it('settings exports ConfigData', async () => {
    const mod = await import('../../shared/config/settings.ts')
    expect(mod.settings).toBeDefined()
    expect(mod.settings.ConfigData).toBeDefined()
  })

  it('AxiosClient exports', async () => {
    const mod = await import('../../shared/api/AxiosClient.ts')
    expect(mod).toBeDefined()
  })

  it('menu exports', async () => {
    const mod = await import('../../shared/lib/menu.ts')
    expect(mod).toBeDefined()
  })
})

describe('Theme module imports', () => {
  it('exports ThemeProvider and themes', async () => {
    const mod = await import('../../app/providers/theme/index.ts')
    expect(mod.ThemeProvider).toBeDefined()
    expect(mod.darkTheme).toBeDefined()
    expect(mod.lightTheme).toBeDefined()
  })
})

describe('Auth module imports', () => {
  it('exports AuthProvider and useAuth', async () => {
    const mod = await import('../../features/auth/model/AuthContext.tsx')
    expect(mod.AuthProvider).toBeDefined()
    expect(mod.useAuth).toBeDefined()
  })
})

describe('Store imports', () => {
  it('imageViewerStore exports useImageViewerStore', async () => {
    const mod = await import('../../features/image-viewer/model/imageViewerStore.ts')
    expect(mod.useImageViewerStore).toBeDefined()
    expect(typeof mod.useImageViewerStore).toBe('function')
  })
})

describe('Service imports', () => {
  it('ImagesService exports', async () => {
    const mod = await import('../../features/image-viewer/api/ImagesService.ts')
    expect(mod).toBeDefined()
  })

  it('CtfRestService exports', async () => {
    const mod = await import('../../features/ctf-analysis/api/CtfRestService.ts')
    expect(mod).toBeDefined()
  })

  it('ParticlePickingRestService exports', async () => {
    const mod = await import('../../features/particle-picking/api/ParticlePickingRestService.ts')
    expect(mod).toBeDefined()
  })
})
