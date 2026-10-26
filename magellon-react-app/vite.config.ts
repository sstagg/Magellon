import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    setupFiles: ['./src/__tests__/setup.ts'],
  },
  server: {
    port: 8080,
    // Mirror nginx.conf: the app calls the backend with relative paths, so
    // `npm run dev` forwards the same routes to the local CoreService.
    proxy: {
      '/socket.io': { target: 'http://localhost:8000', ws: true },
      '^/web/ws/': { target: 'http://localhost:8000', ws: true },
      '^/(health|db|export|image|web|graphs|io|pipelines|artifacts|auth|plugins|cancellation|admin|deployment|dispatch|particle-picking|system|graphql|docs|redoc|openapi\\.json)(/|$)': {
        target: 'http://localhost:8000',
      },
    },
  },
  define: {
    global: 'globalThis',
    'process.env': {}   // THIS FIXES THE ERROR
  },
  optimizeDeps: {
    include: ['socket.io-client'],
    esbuildOptions: {
      define: {
        global: 'globalThis',
      },
    },
  },
  build: {
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },
})
