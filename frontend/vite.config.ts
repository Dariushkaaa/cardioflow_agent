import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Адрес бэкенда для dev-сервера (npm run dev). В Docker запросы проксирует nginx (см. nginx.conf).
const backend = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@app': path.resolve(__dirname, './src/app'),
            '@pages': path.resolve(__dirname, './src/pages'),
            '@widgets': path.resolve(__dirname, './src/widgets'),
            '@features': path.resolve(__dirname, './src/features'),
            '@entities': path.resolve(__dirname, './src/entities'),
            '@shared': path.resolve(__dirname, './src/shared'),
        },
    },
    server: {
        host: true,
        port: 5173,
        proxy: {
            '/api': { target: backend, changeOrigin: true },
            '/ws': { target: backend.replace(/^http/, 'ws'), ws: true, changeOrigin: true },
        },
    },
});
