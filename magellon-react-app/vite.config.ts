import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 8080, // Specify the port number you want to use
  },
  define: {
    // Polyfill global and process for packages that expect Node.js environment
    global: 'globalThis',
    'process.env': 'globalThis.process?.env || {}',
  },
  optimizeDeps: {
    esbuildOptions: {
      define: {
        global: 'globalThis',
      },
    },
  },
})
