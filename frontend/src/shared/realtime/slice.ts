import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { ChatMessage, PatientStatus, RiskLevel, WsMeasurementEvent } from '../api/types';
import { uid } from '../lib/uid';

export interface LiveMeasurement {
    systolic: number | null;
    diastolic: number | null;
    pulse: number | null;
    risk: RiskLevel;
}

interface RealtimeState {
    connected: boolean;
    messages: ChatMessage[];
    waitingForAgent: boolean;
    onboardingRequested: boolean;
    measurement: LiveMeasurement | null;
    patientStatus: PatientStatus;
    bookingOpen: boolean;
    bookingReason: string | null;
}

const initialState: RealtimeState = {
    connected: false,
    messages: [],
    waitingForAgent: false,
    onboardingRequested: false,
    measurement: null,
    patientStatus: 'active',
    bookingOpen: false,
    bookingReason: null,
};

const realtimeSlice = createSlice({
    name: 'realtime',
    initialState,
    reducers: {
        setConnected(state, action: PayloadAction<boolean>) {
            state.connected = action.payload;
        },
        patientMessageSent(state, action: PayloadAction<string>) {
            state.messages.push({
                id: uid(),
                sender: 'patient',
                text: action.payload,
                timestamp: new Date().toISOString(),
            });
            state.waitingForAgent = true;
        },
        agentMessageReceived(state, action: PayloadAction<{ text: string; quick_replies?: string[] }>) {
            state.messages.push({
                id: uid(),
                sender: 'agent',
                text: action.payload.text,
                timestamp: new Date().toISOString(),
                quick_replies: action.payload.quick_replies ?? [],
            });
            state.waitingForAgent = false;
        },
        waitingChanged(state, action: PayloadAction<boolean>) {
            state.waitingForAgent = action.payload;
        },
        onboardingRequested(state) {
            state.onboardingRequested = true;
            state.waitingForAgent = true;
        },
        measurementReceived(state, action: PayloadAction<WsMeasurementEvent['data']>) {
            const prev = state.measurement;
            const { systolic, diastolic, pulse, risk_status } = action.payload;
            // В отчете может быть только пульс или только давление: не затираем старые значения пустыми
            state.measurement = {
                systolic: systolic ?? prev?.systolic ?? null,
                diastolic: diastolic ?? prev?.diastolic ?? null,
                pulse: pulse ?? prev?.pulse ?? null,
                risk: risk_status,
            };
        },
        patientStatusChanged(state, action: PayloadAction<PatientStatus>) {
            state.patientStatus = action.payload;
        },
        bookingRequested(state, action: PayloadAction<string | null>) {
            state.bookingOpen = true;
            state.bookingReason = action.payload;
        },
        bookingClosed(state) {
            state.bookingOpen = false;
        },
    },
});

export const {
    setConnected,
    patientMessageSent,
    agentMessageReceived,
    waitingChanged,
    onboardingRequested,
    measurementReceived,
    patientStatusChanged,
    bookingRequested,
    bookingClosed,
} = realtimeSlice.actions;

export const realtimeReducer = realtimeSlice.reducer;
export type { RealtimeState };
