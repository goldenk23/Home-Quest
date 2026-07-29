import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

/**
 * Scans public/walls/ for .glb files and writes public/walls/manifest.json.
 * Runs on dev-server start, production build, and whenever a .glb is added/removed.
 * This lets the app discover any dropped GLB without a fixed filename.
 */
function wallsManifestPlugin(): Plugin {
  const wallsDir = path.resolve('./public/walls')
  const manifestPath = path.join(wallsDir, 'manifest.json')

  const isGlbOrGltf = (f: string) => f.toLowerCase().endsWith('.glb') || f.toLowerCase().endsWith('.gltf')

  const writeManifest = () => {
    if (!fs.existsSync(wallsDir)) fs.mkdirSync(wallsDir, { recursive: true })
    const results: string[] = []
    // Scan top-level files AND one level of subfolders (Poly Haven downloads
    // come as a folder containing the .gltf + .bin + textures/).
    for (const entry of fs.readdirSync(wallsDir)) {
      const full = path.join(wallsDir, entry)
      const stat = fs.statSync(full)
      if (stat.isFile() && isGlbOrGltf(entry)) {
        results.push(entry)
      } else if (stat.isDirectory()) {
        for (const child of fs.readdirSync(full)) {
          if (isGlbOrGltf(child) && fs.statSync(path.join(full, child)).isFile()) {
            results.push(`${entry}/${child}`)
          }
        }
      }
    }
    fs.writeFileSync(manifestPath, JSON.stringify(results))
  }

  return {
    name: 'walls-manifest',
    buildStart: writeManifest,
    configureServer(server) {
      writeManifest()
      server.watcher.add(wallsDir)
      server.watcher.on('add',   (f) => { if (isGlbOrGltf(f)) writeManifest() })
      server.watcher.on('unlink',(f) => { if (isGlbOrGltf(f)) writeManifest() })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    wallsManifestPlugin(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:3000',
    },
  },
})
