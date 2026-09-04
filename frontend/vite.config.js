import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// This repository lives on a Windows drive (/mnt/c/...). Running the dev server
// from WSL there means inotify never fires, so edits silently fail to hot-reload
// until the server is restarted. Polling is the reliable option on that setup;
// set VITE_NO_POLLING=1 to turn it off when running on a native Linux or macOS
// filesystem, where the default watcher is both cheaper and sufficient.
const usePolling = process.env.VITE_NO_POLLING !== '1'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: usePolling ? { usePolling: true, interval: 400 } : undefined,
  },
})
