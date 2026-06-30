import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import pkg from "./package.json"

const backendPort = parseInt(process.env.BACKEND_PORT || '5611')
const devPort = parseInt(process.env.DEV_PORT || '8802')

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [
    react(),
    {
      // Dev-only: rewrite /static/* → /* so public/ assets (sprites, icons) resolve
      // correctly without the /static/ prefix that the production FastAPI server adds.
      name: "static-rewrite",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url?.startsWith("/static/")) {
            req.url = req.url.slice("/static".length)
          }
          next()
        })
      },
    },
  ],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        chunkFileNames: `assets/[name]-[hash]-${Date.now()}.js`,
        assetFileNames: `assets/[name]-[hash]-${Date.now()}.[ext]`
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: devPort,
    allowedHosts: true,  // Allow all hosts for flexible deployment
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://127.0.0.1:${backendPort}`,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./app"),
    },
  },
})
