export type RiskLevel = 'stable' | 'warning' | 'critical';
export type PatientStatus = 'active' | 'lost_to_follow_up';

export interface TreatmentPlan {
    patient_id: string;
    full_name: string;
    doctor_name: string;
    prescribed_medication: string | null;
    frequency_per_day: number;
    target_systolic: number;
    target_diastolic: number;
    morning_time: string | null; // "HH:MM:SS"
    evening_time: string | null;
}

export interface LatestMeasurement {
    systolic: number | null;
    diastolic: number | null;
    pulse: number | null;
    risk_status: RiskLevel;
    timestamp: string;
}

/** Точка на графике: замер из истории (GET /patient/measurements) или из события WebSocket. */
export interface Measurement {
    id: string;
    systolic: number | null;
    diastolic: number | null;
    pulse: number | null;
    risk_status: RiskLevel;
    timestamp: string; // ISO без часового пояса (время пациента), например "2026-10-05T12:30:00"
}

export interface ReportPayload {
    patient_id: string;
    systolic?: number | null;
    diastolic?: number | null;
    pulse?: number | null;
    medication_taken?: boolean | null;
    skip_reason?: string | null;
    raw_complaint?: string | null;
}

export interface ReportResult {
    status: string;
    risk_level: string;
    action_required: string;
    message: string;
}

export interface AppointmentSlot {
    id: string;
    doctor_name: string;
    datetime: string;
}

export interface SchedulePayload {
    patient_id: string;
    morning_time: string; // "HH:MM:SS"
    evening_time: string;
}

export interface ChatMessage {
    id: string;
    sender: 'patient' | 'agent';
    text: string;
    timestamp: string;
    quick_replies?: string[];
}

export interface WsMeasurementEvent {
    event: 'new_measurement_status';
    data: {
        id?: string;
        timestamp?: string;
        systolic: number | null;
        diastolic: number | null;
        pulse: number | null;
        risk_status: RiskLevel;
    };
}

export interface WsAgentMessageEvent {
    event: 'agent_message';
    data: {
        text: string;
        quick_replies?: string[];
    };
}

export interface WsShowSlotsEvent {
    event: 'show_appointment_slots';
    data: {
        reason: string;
    };
}

export interface WsPatientStatusEvent {
    event: 'patient_status_update';
    data: {
        status: PatientStatus;
    };
}

export interface WsErrorEvent {
    event: 'error';
    data: {
        message: string;
    };
}

export type WsIncomingServerMessage =
    | WsMeasurementEvent
    | WsAgentMessageEvent
    | WsShowSlotsEvent
    | WsPatientStatusEvent
    | WsErrorEvent;
