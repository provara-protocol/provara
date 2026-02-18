import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import wasm from '@vitejs/plugin-wasm';

export default defineConfig({
  plugins: [react(), wasm()],
  server: {
    port: 5173,
    open: true,
  },
  build: {
    target: 'esnext',
    minify: 'terser',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['react', 'react-dom'],
        }
      }
    }
  },
  optimizeDeps: {
    exclude: ['@provara/core'],
  }
});
