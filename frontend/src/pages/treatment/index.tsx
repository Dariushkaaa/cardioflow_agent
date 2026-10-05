import React, { useEffect, useState } from 'react';
import { errorMessage, useGetTreatmentPlanQuery, useUpdateScheduleMutation } from '@shared/api/baseApi';
import { PATIENT_ID } from '@shared/config';

const card: React.CSSProperties = {
    background: '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
};

const input: React.CSSProperties = {
    padding: '8px 12px',
    borderRadius: 10,
    border: '1px solid #CBD5E1',
    fontSize: 15,
};

export const TreatmentPage: React.FC = () => {
    const { data: plan, isLoading, isError } = useGetTreatmentPlanQuery();
    const [updateSchedule, { isLoading: isSaving, isSuccess, error, reset }] = useUpdateScheduleMutation();
    const [morning, setMorning] = useState('09:00');
    const [evening, setEvening] = useState('21:00');

    useEffect(() => {
        if (plan?.morning_time) setMorning(plan.morning_time.slice(0, 5));
        if (plan?.evening_time) setEvening(plan.evening_time.slice(0, 5));
    }, [plan?.morning_time, plan?.evening_time]);

    const onSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        void updateSchedule({
            patient_id: PATIENT_ID,
            morning_time: `${morning}:00`,
            evening_time: `${evening}:00`,
        });
    };

    return (
        <div style={{ padding: '16px' }}>
            <h2 style={{ marginBottom: 16 }}>Лечение</h2>

            {isLoading && <p>Загрузка...</p>}
            {isError && <p>Не удалось загрузить план терапии.</p>}

            {plan && (
                <div style={card}>
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>План терапии</div>
                    <div>Врач: {plan.doctor_name}</div>
                    <div>Препарат: {plan.prescribed_medication ?? 'не назначен'}</div>
                    <div>Приемов в день: {plan.frequency_per_day}</div>
                    <div>
                        Целевое давление: {plan.target_systolic}/{plan.target_diastolic}
                    </div>
                </div>
            )}

            <form style={card} onSubmit={onSubmit}>
                <div style={{ fontWeight: 600, marginBottom: 12 }}>Расписание приема</div>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
                    <label>
                        <div style={{ fontSize: 13, color: '#64748B', marginBottom: 4 }}>Утро</div>
                        <input
                            type="time"
                            style={input}
                            value={morning}
                            required
                            onChange={(e) => {
                                reset();
                                setMorning(e.target.value);
                            }}
                        />
                    </label>
                    <label>
                        <div style={{ fontSize: 13, color: '#64748B', marginBottom: 4 }}>Вечер</div>
                        <input
                            type="time"
                            style={input}
                            value={evening}
                            required
                            onChange={(e) => {
                                reset();
                                setEvening(e.target.value);
                            }}
                        />
                    </label>
                </div>
                <div style={{ fontSize: 12, color: '#64748B', marginBottom: 12 }}>
                    Интервал между приемами должен быть от 8 до 12 часов.
                </div>
                <button
                    type="submit"
                    disabled={isSaving}
                    style={{
                        padding: '10px 20px',
                        borderRadius: 12,
                        border: 'none',
                        background: '#2563EB',
                        color: '#fff',
                        cursor: 'pointer',
                    }}
                >
                    Сохранить
                </button>
                {isSuccess && <span style={{ marginLeft: 12, color: '#10B981' }}>Расписание сохранено</span>}
                {error !== undefined && (
                    <div style={{ marginTop: 12, color: '#EF4444', fontSize: 14 }}>
                        {errorMessage(error, 'Не удалось сохранить расписание')}
                    </div>
                )}
            </form>
        </div>
    );
};
