import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8080,
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
