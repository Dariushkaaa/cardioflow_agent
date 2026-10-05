import React from 'react';
import { CHART_LIMIT, useGetMeasurementHistoryQuery, useGetTreatmentPlanQuery } from '@shared/api/baseApi';
import { MeasurementChart, formatChartTime } from '@widgets/measurement-chart';

const RISK_LABEL: Record<string, string> = { stable: 'в норме', warning: 'выше целевого', critical: 'риск' };

export const StatsPage: React.FC = () => {
    const { data: treatment } = useGetTreatmentPlanQuery();
    const { data: history = [], isLoading } = useGetMeasurementHistoryQuery(CHART_LIMIT);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h2 style={{ margin: 0 }}>Аналитика АД</h2>
            <div style={{ background: '#fff', borderRadius: 16, padding: 16 }}>
                <MeasurementChart
                    data={history}
                    targetSystolic={treatment?.target_systolic}
                    targetDiastolic={treatment?.target_diastolic}
                    isLoading={isLoading}
                />
            </div>
            {history.length > 0 && (
                <div style={{ background: '#fff', borderRadius: 16, padding: 16, fontSize: 14 }}>
                    {[...history].reverse().map((m) => (
                        <div
                            key={m.id}
                            style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #F1F5F9' }}
                        >
                            <span>{formatChartTime(m.timestamp)}</span>
                            <span>
                                {m.systolic ?? '—'}/{m.diastolic ?? '—'}
                                {m.pulse !== null ? `, пульс ${m.pulse}` : ''}
                            </span>
                            <span>{RISK_LABEL[m.risk_status] ?? m.risk_status}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
