import { PATIENT_ID } from '../config';

const TOKEN_KEY = 'jwt_token';
const EXPIRES_KEY = 'jwt_expires_at';
const REFRESH_SKEW_MS = 60_000; // обновляем токен за минуту до истечения

function read(key: string): string | null {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function write(key: string, value: string): void {
    try {
        localStorage.setItem(key, value);
    } catch {
        // localStorage недоступен: токен будет жить только в памяти
    }
}

let memoryToken = '';
let memoryExpiresAt = 0;
let inflight: Promise<string> | null = null;

export function getToken(): string {
    return memoryToken || read(TOKEN_KEY) || '';
}

function expiresAt(): number {
    return memoryExpiresAt || Number(read(EXPIRES_KEY) || 0);
}

function isFresh(): boolean {
    return Boolean(getToken()) && expiresAt() - Date.now() > REFRESH_SKEW_MS;
}

/** Запрашивает новый JWT у бэкенда (POST /api/v1/auth/token). */
export async function refreshToken(): Promise<string> {
    if (inflight) return inflight;
    inflight = (async () => {
        const response = await fetch('/api/v1/auth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: PATIENT_ID }),
        });
        if (!response.ok) {
            throw new Error(`Не удалось получить токен (HTTP ${response.status})`);
        }
        const data = (await response.json()) as { access_token: string; expires_in: number };
        memoryToken = data.access_token;
        memoryExpiresAt = Date.now() + data.expires_in * 1000;
        write(TOKEN_KEY, memoryToken);
        write(EXPIRES_KEY, String(memoryExpiresAt));
        return memoryToken;
    })().finally(() => {
        inflight = null;
    });
    return inflight;
}

/** Возвращает действующий токен, при необходимости обновляя его. */
export async function ensureToken(): Promise<string> {
    return isFresh() ? getToken() : refreshToken();
}
