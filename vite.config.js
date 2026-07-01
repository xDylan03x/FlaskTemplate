import { defineConfig } from 'vite'

export default defineConfig({
    build: {
        outDir: 'app/core/static/dist',
        emptyOutDir: true,
        rollupOptions: {
            input: 'app/core/static/js/uploader.js',
            output: {
                entryFileNames: 'uploader.js',
                assetFileNames: 'uploader.[ext]',
            },
        },
    },
})