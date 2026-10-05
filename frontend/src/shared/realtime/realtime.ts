import type { AppDispatch } from '@app/store';
import { ensureToken, refreshToken } from '../api/auth';
import { baseApi, CHART_LIMIT } from '../api/baseApi';
import type { Measurement, WsIncomingServerMessage, WsMeasurementEvent } from '../api/types';
import {
    agentMessageReceived,
    bookingRequested,
    measurementReceived,
    patientStatusChanged,
    setConnected,
    waitingChanged,
} from './slice';

const WS_POLICY_VIOLATION = 4008; // сервер закрывает сокет с этим кодом при невалидном токене
const MAX_RETRY_DELAY_MS = 10_000;
const AGENT_WAIT_TIMEOUT_MS = 35_000;

let socket: WebSocket | null = null;
let generation = 0;
let retryTimer: ReturnType<typeof setTimeout> | undefined;
let waitTimer: ReturnType<typeof setTimeout> | undefined;
let retries = 0;

function wsUrl(patientId: string, token: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}/ws/patient/${patientId}?token=${encodeURIComponent(token)}`;
}

/** Время пациента без часового пояса в формате ISO: так же, как отдает бэкенд (запасной вариант, если сервер не прислал timestamp). */
function localIsoNow(): string {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

/**
 * Новый замер из WebSocket: сразу дописываем точку в кэш графика (без ожидания HTTP-запроса),
 * затем помечаем историю устаревшей - RTK Query перечитает ее с сервера и сверит по id (дубликатов нет).
 */
function appendMeasurementToChart(dispatch: AppDispatch, data: WsMeasurementEvent['data']): void {
    const point: Measurement = {
        id: data.id ?? `ws-${Date.now()}`,
        systolic: data.systolic ?? null,
        diastolic: data.diastolic ?? null,
        pulse: data.pulse ?? null,
        risk_status: data.risk_status,
        timestamp: data.timestamp ?? localIsoNow(),
    };
    dispatch(
        baseApi.util.updateQueryData('getMeasurementHistory', CHART_LIMIT, (draft) => {
            if (draft.some((item) => item.id === point.id)) return;
            draft.push(point);
            if (draft.length > CHART_LIMIT) draft.splice(0, draft.length - CHART_LIMIT);
        })
    );
    dispatch(baseApi.util.invalidateTags(['Measurements']));
}

function handleMessage(dispatch: AppDispatch, raw: string): void {
    let payload: WsIncomingServerMessage;
    try {
        payload = JSON.parse(raw) as WsIncomingServerMessage;
    } catch {
        return;
    }
    switch (payload.event) {
        case 'agent_message':
            clearTimeout(waitTimer);
            dispatch(agentMessageReceived(payload.data));
            break;
        case 'new_measurement_status':
            dispatch(measurementReceived(payload.data));
            appendMeasurementToChart(dispatch, payload.data);
            break;
        case 'show_appointment_slots':
            // слоты могли измениться с прошлого открытия окна записи
            dispatch(baseApi.util.invalidateTags(['Slots']));
            dispatch(bookingRequested(payload.data.reason ?? null));
            break;
        case 'patient_status_update':
            dispatch(patientStatusChanged(payload.data.status));
            break;
        case 'error':
            clearTimeout(waitTimer);
            dispatch(waitingChanged(false));
            break;
    }
}

async function connect(patientId: string, dispatch: AppDispatch, gen: number): Promise<void> {
    let token: string;
    try {
        token = await ensureToken();
    } catch {
        scheduleReconnect(patientId, dispatch, gen);
        return;
    }
    if (gen !== generation) return; // за время запроса токена сервис остановили/перезапустили

    const ws = new WebSocket(wsUrl(patientId, token));
    socket = ws;

    ws.onopen = () => {
        retries = 0;
        dispatch(setConnected(true));
        // Пока сокет был разорван, замеры могли прийти мимо нас: перечитываем историю при каждом (пере)подключении
        dispatch(baseApi.util.invalidateTags(['Measurements']));
    };
    ws.onmessage = (event: MessageEvent<string>) => handleMessage(dispatch, event.data);
    ws.onerror = () => ws.close();
    ws.onclose = async (event: CloseEvent) => {
        if (socket === ws) socket = null;
        if (gen !== generation) return;
        dispatch(setConnected(false));
        if (event.code === WS_POLICY_VIOLATION) {
            try {
                await refreshToken(); // токен невалиден/просрочен - перевыпускаем перед повтором
            } catch {
                // повторим попытку по таймеру
            }
        }
        scheduleReconnect(patientId, dispatch, gen);
    };
}

function scheduleReconnect(patientId: string, dispatch: AppDispatch, gen: number): void {
    if (gen !== generation) return;
    const delay = Math.min(1000 * 2 ** retries, MAX_RETRY_DELAY_MS);
    retries += 1;
    clearTimeout(retryTimer);
    retryTimer = setTimeout(() => void connect(patientId, dispatch, gen), delay);
}

export const realtime = {
    /** Открывает единственное WebSocket-соединение приложения (чат + события интерфейса). */
    start(patientId: string, dispatch: AppDispatch): void {
        generation += 1;
        retries = 0;
        void connect(patientId, dispatch, generation);
    },

    stop(): void {
        generation += 1;
        clearTimeout(retryTimer);
        clearTimeout(waitTimer);
        const ws = socket;
        socket = null;
        if (ws) {
            ws.onclose = null;
            ws.close();
        }
    },

    isOpen(): boolean {
        return socket?.readyState === WebSocket.OPEN;
    },

    /** Контракт WS бэкенда: {"action": "send_message", "data": {"text": "..."}} */
    sendMessage(text: string, dispatch: AppDispatch): boolean {
        if (!this.isOpen()) return false;
        socket!.send(JSON.stringify({ action: 'send_message', data: { text } }));
        this.armWaitTimeout(dispatch);
        return true;
    },

    /** Просит агента прислать приветствие с назначениями врача. */
    requestOnboarding(dispatch: AppDispatch): boolean {
        if (!this.isOpen()) return false;
        socket!.send(JSON.stringify({ action: 'init_onboarding', data: {} }));
        this.armWaitTimeout(dispatch);
        return true;
    },

    armWaitTimeout(dispatch: AppDispatch): void {
        clearTimeout(waitTimer);
        waitTimer = setTimeout(() => dispatch(waitingChanged(false)), AGENT_WAIT_TIMEOUT_MS);
    },
};
