import React, { useCallback, useEffect, useState } from 'react';
import { ensureToken } from '@shared/api/auth';

type Status = 'loading' | 'ready' | 'error';

/** Не показывает приложение, пока не получен JWT пациента (POST /api/v1/auth/token). */
export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [status, setStatus] = useState<Status>('loading');
    const [message, setMessage] = useState('');

    const load = useCallback(() => {
        setStatus('loading');
        ensureToken()
            .then(() => setStatus('ready'))
            .catch((error: unknown) => {
                setMessage(error instanceof Error ? error.message : 'Неизвестная ошибка');
                setStatus('error');
            });
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    if (status === 'ready') return <>{children}</>;

    return (
        <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24, textAlign: 'center' }}>
            {status === 'loading' ? (
                <div>❤️ CardioFlow: подключение к серверу...</div>
            ) : (
                <div>
                    <p style={{ marginBottom: 8 }}>Не удалось подключиться к серверу.</p>
                    <p style={{ marginBottom: 16, color: '#64748B', fontSize: 14 }}>{message}</p>
                    <button
                        onClick={load}
                        style={{
                            padding: '10px 20px',
                            borderRadius: 12,
                            border: 'none',
                            background: '#2563EB',
                            color: '#fff',
                            cursor: 'pointer',
                        }}
                    >
                        Повторить
                    </button>
                </div>
            )}
        </div>
    );
};
