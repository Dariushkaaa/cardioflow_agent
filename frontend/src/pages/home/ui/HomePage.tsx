import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    CHART_LIMIT,
    errorMessage,
    useGetLatestMeasurementQuery,
    useGetMeasurementHistoryQuery,
    useGetTreatmentPlanQuery,
    useSubmitReportMutation,
} from '@shared/api/baseApi';
import type { RiskLevel } from '@shared/api/types';
import { PATIENT_ID } from '@shared/config';
import { useAppSelector } from '@shared/lib/hooks';
import { MeasurementChart } from '@widgets/measurement-chart';
import styles from './HomePage.module.css';

const RISK_LABEL: Record<RiskLevel, string> = {
    stable: 'В норме',
    warning: 'Выше целевого',
    critical: 'Повышенный риск',
};

const RISK_CLASS: Record<RiskLevel, string> = {
    stable: '',
    warning: styles.statusWarning,
    critical: styles.statusCritical,
};

/** Ближайший прием лекарства по расписанию ("HH:MM:SS"), локальное время браузера. */
function nextDose(morning?: string | null, evening?: string | null): string | null {
    const times = [morning, evening].filter((t): t is string => Boolean(t)).map((t) => t.slice(0, 5));
    if (times.length === 0) return null;
    const now = new Date();
    const current = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const sorted = [...times].sort();
    const upcoming = sorted.find((t) => t > current);
    return upcoming ? `сегодня в ${upcoming}` : `завтра в ${sorted[0]}`;
}

/** Разбирает целое число из поля формы; пустая строка = не указано. */
function toInt(value: string): number | null {
    const trimmed = value.trim();
    return trimmed === '' ? null : Number(trimmed);
}

/** Проверка тех же границ, что у бэкенда (ReportCreate), чтобы не получить 422 от сервера. */
function validateManual(systolic: number | null, diastolic: number | null, pulse: number | null): string | null {
    const values = [systolic, diastolic, pulse];
    if (values.some((v) => v !== null && !Number.isInteger(v))) return 'Введите целые числа.';
    if (systolic === null && diastolic === null && pulse === null) return 'Укажите давление и/или пульс.';
    if ((systolic === null) !== (diastolic === null)) return 'Верхнее и нижнее давление указываются вместе.';
    if (systolic !== null && diastolic !== null) {
        if (systolic < 40 || systolic > 300 || diastolic < 20 || diastolic > 200) return 'Проверьте значения давления.';
        if (systolic <= diastolic) return 'Верхнее давление должно быть больше нижнего.';
    }
    if (pulse !== null && (pulse < 20 || pulse > 250)) return 'Проверьте значение пульса.';
    return null;
}

export const HomePage: React.FC = () => {
    const navigate = useNavigate();
    const { data: treatment } = useGetTreatmentPlanQuery();
    const { data: latest } = useGetLatestMeasurementQuery();
    // График читает историю из кэша RTK Query: WebSocket-событие new_measurement_status дописывает точку мгновенно
    const { data: history = [], isLoading: historyLoading } = useGetMeasurementHistoryQuery(CHART_LIMIT);
    const [submitReport, { isLoading: isSubmitting }] = useSubmitReportMutation();
    const [form, setForm] = useState({ systolic: '', diastolic: '', pulse: '' });
    const [formMessage, setFormMessage] = useState<{ ok: boolean; text: string } | null>(null);

    const handleManualSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        const systolic = toInt(form.systolic);
        const diastolic = toInt(form.diastolic);
        const pulse = toInt(form.pulse);
        const problem = validateManual(systolic, diastolic, pulse);
        if (problem) {
            setFormMessage({ ok: false, text: problem });
            return;
        }
        try {
            const result = await submitReport({ patient_id: PATIENT_ID, systolic, diastolic, pulse }).unwrap();
            setForm({ systolic: '', diastolic: '', pulse: '' });
            setFormMessage({ ok: true, text: result.message });
        } catch (error) {
            setFormMessage({ ok: false, text: errorMessage(error, 'Не удалось сохранить замер') });
        }
    };
    const live = useAppSelector((state) => state.realtime.measurement);
    const patientStatus = useAppSelector((state) => state.realtime.patientStatus);

    // Свежие данные из WebSocket важнее сохраненного последнего замера
    const measurement = live ?? (latest
        ? { systolic: latest.systolic, diastolic: latest.diastolic, pulse: latest.pulse, risk: latest.risk_status }
        : null);

    const firstName = treatment?.full_name ? treatment.full_name.split(' ')[1] : null;
    const dose = nextDose(treatment?.morning_time, treatment?.evening_time);

    return (
        <div className={styles.homePage}>
            <header className={styles.header}>
                <div>
                    <h1 className={styles.greetingTitle}>Здравствуйте{firstName ? `, ${firstName}` : ''}!</h1>
                    {treatment && (
                        <span className={styles.diagnosisTag}>
                            Целевое давление {treatment.target_systolic}/{treatment.target_diastolic}
                            {treatment.prescribed_medication ? ` • ${treatment.prescribed_medication}` : ''}
                        </span>
                    )}
                </div>
            </header>

            {patientStatus === 'lost_to_follow_up' && (
                <div className={styles.reminderCard}>
                    <div style={{ fontSize: '13px', color: '#4C0519' }}>
                        Давно не было данных от вас. Напишите в чат, как вы себя чувствуете.
                    </div>
                </div>
            )}

            <div className={styles.dashboardGrid}>
                {/* Карточка текущего статуса АД */}
                <div className={styles.metricCard}>
                    <div className={styles.metricHeader}>
                        <span>Ваши показатели</span>
                        {measurement && (
                            <span className={`${styles.statusBadge} ${RISK_CLASS[measurement.risk]}`}>
                                ● {RISK_LABEL[measurement.risk]}
                            </span>
                        )}
                    </div>

                    {measurement ? (
                        <>
                            <div className={styles.metricValues}>
                                <span className={styles.mainValue}>
                                    {measurement.systolic ?? '—'}/{measurement.diastolic ?? '—'}
                                </span>
                                <span className={styles.unit}>мм рт. ст.</span>
                            </div>
                            <div style={{ fontSize: '14px', color: '#64748B' }}>
                                Пульс <strong>{measurement.pulse ?? '—'}</strong> уд/мин
                            </div>
                        </>
                    ) : (
                        <div style={{ fontSize: '14px', color: '#64748B' }}>
                            Замеров пока нет. Отправьте давление в чат, например: «Давление 130/85, пульс 72».
                        </div>
                    )}
                </div>

                {/* График давления: обновляется сам после каждого нового замера (чат, форма ниже, агент) */}
                <div className={styles.metricCard} style={{ gridColumn: '1 / -1' }}>
                    <div className={styles.metricHeader}>
                        <span>Динамика давления</span>
                    </div>
                    <MeasurementChart
                        data={history}
                        targetSystolic={treatment?.target_systolic}
                        targetDiastolic={treatment?.target_diastolic}
                        isLoading={historyLoading}
                    />
                </div>

                {/* Ручной ввод замера */}
                <form className={styles.metricCard} onSubmit={handleManualSubmit}>
                    <div className={styles.metricHeader}>
                        <span>Добавить замер</span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px', alignItems: 'center' }}>
                        <input
                            type="number"
                            inputMode="numeric"
                            placeholder="Верхнее"
                            aria-label="Верхнее давление"
                            value={form.systolic}
                            onChange={(e) => setForm({ ...form, systolic: e.target.value })}
                            style={{ width: '90px', padding: '8px', borderRadius: '8px', border: '1px solid #CBD5E1' }}
                        />
                        <span>/</span>
                        <input
                            type="number"
                            inputMode="numeric"
                            placeholder="Нижнее"
                            aria-label="Нижнее давление"
                            value={form.diastolic}
                            onChange={(e) => setForm({ ...form, diastolic: e.target.value })}
                            style={{ width: '90px', padding: '8px', borderRadius: '8px', border: '1px solid #CBD5E1' }}
                        />
                        <input
                            type="number"
                            inputMode="numeric"
                            placeholder="Пульс"
                            aria-label="Пульс"
                            value={form.pulse}
                            onChange={(e) => setForm({ ...form, pulse: e.target.value })}
                            style={{ width: '90px', padding: '8px', borderRadius: '8px', border: '1px solid #CBD5E1' }}
                        />
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className={styles.actionButton}
                            style={{ flexDirection: 'row', padding: '8px 16px', width: 'auto' }}
                        >
                            {isSubmitting ? 'Сохраняю...' : 'Сохранить'}
                        </button>
                    </div>
                    {formMessage && (
                        <div style={{ marginTop: '8px', fontSize: '13px', color: formMessage.ok ? '#059669' : '#EF4444' }}>
                            {formMessage.text}
                        </div>
                    )}
                </form>

                {/* Напоминание о приеме лекарств */}
                {dose && (
                    <div className={styles.reminderCard}>
                        <div>
                            <div style={{ fontWeight: 600, color: '#BE123C' }}>Напоминание</div>
                            <div style={{ fontSize: '13px', color: '#4C0519', marginTop: '2px' }}>
                                Следующий прием препарата {dose}
                            </div>
                        </div>
                        <span style={{ fontSize: '20px' }}>›</span>
                    </div>
                )}
            </div>

            <div style={{ fontWeight: 600, marginTop: '8px' }}>Быстрые действия</div>
            <div className={styles.quickActionsGrid}>
                <button className={styles.actionButton} onClick={() => navigate('/chat')}>
                    <span>💬</span>
                    <span>Написать в чат</span>
                </button>
                <button className={styles.actionButton} onClick={() => navigate('/treatment')}>
                    <span>💊</span>
                    <span>План лечения</span>
                </button>
            </div>
        </div>
    );
};
