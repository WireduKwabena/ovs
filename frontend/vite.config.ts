import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from "path"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

// frontend/vite.config.ts
  resolve: {
    preserveSymlinks: true,
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/services': path.resolve(__dirname, './src/services'),
      '@/store': path.resolve(__dirname, './src/store'),
      '@/types': path.resolve(__dirname, './src/types'),
      '@/utils': path.resolve(__dirname, './src/utils'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: 'index.html',
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')

          if (normalizedId.includes('@heygen/streaming-avatar') || normalizedId.includes('@heygen/liveavatar-web-sdk')) {
            return 'heygen-sdk'
          }
          if (normalizedId.includes('livekit-client')) {
            return 'livekit-client'
          }
          if (normalizedId.includes('@protobufjs') || normalizedId.includes('protobufjs')) {
            return 'protobuf'
          }
          if (normalizedId.includes('recordrtc')) {
            return 'recordrtc'
          }
          if (normalizedId.includes('/node_modules/recharts/')) {
            return 'recharts'
          }
          if (
            normalizedId.includes('/node_modules/react/') ||
            normalizedId.includes('/node_modules/react-dom/') ||
            normalizedId.includes('/node_modules/scheduler/')
          ) {
            return 'react-core'
          }
          if (
            normalizedId.includes('/node_modules/react-router/') ||
            normalizedId.includes('/node_modules/react-router-dom/')
          ) {
            return 'react-router'
          }
          if (
            normalizedId.includes('/node_modules/@reduxjs/toolkit/') ||
            normalizedId.includes('/node_modules/react-redux/') ||
            normalizedId.includes('/node_modules/redux-persist/')
          ) {
            return 'state-data'
          }
          if (
            normalizedId.includes('/node_modules/@tanstack/react-query/') ||
            normalizedId.includes('/node_modules/@tanstack/query-core/') ||
            normalizedId.includes('/node_modules/axios/')
          ) {
            return 'query-data'
          }
          if (
            normalizedId.includes('/node_modules/@radix-ui/') ||
            normalizedId.includes('/node_modules/@dnd-kit/') ||
            normalizedId.includes('/node_modules/lucide-react/')
          ) {
            return 'ui-kit'
          }
          if (
            normalizedId.includes('/node_modules/react-hook-form/') ||
            normalizedId.includes('/node_modules/@hookform/') ||
            normalizedId.includes('/node_modules/yup/')
          ) {
            return 'forms'
          }
          return undefined
        },
      },
    },
  },
})


