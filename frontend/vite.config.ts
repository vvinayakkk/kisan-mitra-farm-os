import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";


export default defineConfig(() => ({
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: ["raspberrypi.local", "localhost", "127.0.0.1"],
    hmr: {
      overlay: false,
    },


    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/admin": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/webhook": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/docs": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  plugins: [
    react(),
    {
      name: "skyview-offline-static-manifest",
      generateBundle(_, bundle) {
        const assets = Object.keys(bundle)
          .filter((name) =>
            /^assets\/.*\.(?:js|css|woff2?|svg|png)$/.test(name),
          )
          .map((name) => "/" + name);
        this.emitFile({
          type: "asset",
          fileName: "offline-assets.json",
          source: JSON.stringify({ assets }),
        });
        const fingerprint = createHash("sha256")
          .update(assets.join("\n"))
          .digest("hex")
          .slice(0, 16);
        const worker = readFileSync(
          path.resolve(__dirname, "public/offline-worker.js"),
          "utf8",
        ).replace(
          /const CACHE = "skyview-shell-[^"]+";/,
          `const CACHE = "skyview-shell-${fingerprint}";`,
        );
        this.emitFile({
          type: "asset",
          fileName: "offline-worker.js",
          source: worker,
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
