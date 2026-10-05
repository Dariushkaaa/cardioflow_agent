import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { BaseQueryFn, FetchArgs, FetchBaseQueryError } from '@reduxjs/toolkit/query/react';
import { ensureToken, getToken, refreshToken } from './auth';
import type {
    AppointmentSlot,
    LatestMeasurement,
    Measurement,
    ReportPayload,
    ReportResult,
    SchedulePayload,
    TreatmentPlan,
} from './types';

/** Сколько последних замеров показывает график (один и тот же аргумент у запроса и у ручного обновления кэша). */
export const CHART_LIMIT = 30;

const rawBaseQuery = fetchBaseQuery({
    baseUrl: '/api/v1',
    prepareHeaders: (headers) => {
        const token = getToken();
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
        }
        return headers;
    },
});

/** Перед запросом обновляет JWT (живет ~30 мин), а при 401 один раз перевыпускает токен и повторяет запрос. */
const baseQueryWithReauth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
    args,
    api,
    extraOptions
) => {
    try {
        await ensureToken();
    } catch {
        return { error: { status: 'FETCH_ERROR', error: 'Не удалось получить токен' } };
    }
    let result = await rawBaseQuery(args, api, extraOptions);
    if (result.error?.status === 401) {
        try {
            await refreshToken();
            result = await rawBaseQuery(args, api, extraOptions);
        } catch {
            // оставляем исходную 401
        }
    }
    return result;
};

export const baseApi = createApi({
    reducerPath: 'api',
    baseQuery: baseQueryWithReauth,
    tagTypes: ['TreatmentPlan', 'Slots', 'Appointments', 'Measurements'],
    endpoints: (builder) => ({
        getTreatmentPlan: builder.query<TreatmentPlan, void>({
            query: () => '/patient/treatment-plan',
            providesTags: ['TreatmentPlan'],
        }),

        getLatestMeasurement: builder.query<LatestMeasurement | null, void>({
            query: () => '/patient/measurements/latest',
            providesTags: ['Measurements'],
        }),

        /** История замеров для графика на главной: по возрастанию времени. */
        getMeasurementHistory: builder.query<Measurement[], number>({
            query: (limit) => ({ url: '/patient/measurements', params: { limit } }),
            providesTags: ['Measurements'],
        }),

        /** Ручной ввод замера (кнопка на главной): тот же POST /reports/, что вызывает агент. */
        submitReport: builder.mutation<ReportResult, ReportPayload>({
            query: (body) => ({ url: '/reports/', method: 'POST', body }),
            // График и карточка перечитают историю; точку мгновенно добавит и WebSocket-событие
            invalidatesTags: ['Measurements'],
        }),

        getAvailableSlots: builder.query<AppointmentSlot[], { doctorType?: string; limit?: number }>({
            query: ({ doctorType = 'therapist', limit = 3 }) => ({
                url: '/slots/available',
                params: { doctor_type: doctorType, limit },
            }),
            transformResponse: (response: { slots: AppointmentSlot[] }) => response.slots,
            providesTags: ['Slots'],
        }),

        bookAppointment: builder.mutation<
            { status: string; slot_id: string; datetime: string },
            { patient_id: string; slot_id: string }
        >({
            query: (body) => ({
                url: '/appointments/book',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['Slots', 'Appointments'],
        }),

        updateSchedule: builder.mutation<{ status: string }, SchedulePayload>({
            query: (body) => ({
                url: '/patient/schedule',
                method: 'POST',
                body,
            }),
            invalidatesTags: ['TreatmentPlan'],
        }),
    }),
});

export const {
    useGetTreatmentPlanQuery,
    useGetLatestMeasurementQuery,
    useGetMeasurementHistoryQuery,
    useSubmitReportMutation,
    useGetAvailableSlotsQuery,
    useBookAppointmentMutation,
    useUpdateScheduleMutation,
} = baseApi;

/** Достает человекочитаемую причину ошибки из ответа бэкенда ({"detail": "..."}). */
export function errorMessage(error: unknown, fallback = 'Что-то пошло не так'): string {
    if (error && typeof error === 'object' && 'data' in error) {
        const data = (error as { data?: unknown }).data;
        if (data && typeof data === 'object' && 'detail' in data) {
            const detail = (data as { detail?: unknown }).detail;
            if (typeof detail === 'string') return detail;
            if (Array.isArray(detail) && detail.length > 0) {
                // 422 от FastAPI: [{ loc: [...], msg: '...' }]
                const first = detail[0] as { msg?: unknown };
                if (typeof first?.msg === 'string') return first.msg;
            }
        }
    }
    return fallback;
}
