import React, { useMemo } from 'react';
import type { Measurement, RiskLevel } from '@shared/api/types';
import styles from './MeasurementChart.module.css';

interface MeasurementChartProps {
    data: Measurement[];
    targetSystolic?: number;
    targetDiastolic?: number;
    isLoading?: boolean;
}

const WIDTH = 640;
const HEIGHT = 260;
const PAD = { top: 16, right: 16, bottom: 34, left: 40 };

const RISK_COLOR: Record<RiskLevel, string> = {
    stable: '#10B981',
    warning: '#F59E0B',
    critical: '#EF4444',
};
const SYSTOLIC_COLOR = '#E11D48';
const DIASTOLIC_COLOR = '#2563EB';

/** "2026-10-05T12:30:00" -> "05.10 12:30" (строкой, без Date: время уже в поясе пациента). */
export function formatChartTime(timestamp: string): string {
    const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(timestamp);
    return m ? `${m[3]}.${m[2]} ${m[4]}:${m[5]}` : timestamp;
}

function linePath(points: Array<{ x: number; y: number } | null>): string {
    let d = '';
    let penDown = false;
    for (const p of points) {
        if (!p) {
            penDown = false; // замер без давления (только пульс) разрывает линию
            continue;
        }
        d += `${penDown ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)} `;
        penDown = true;
    }
    return d.trim();
}

/** График давления без внешних библиотек (SVG): перерисовывается сам, когда меняются данные в Redux-кэше. */
export const MeasurementChart: React.FC<MeasurementChartProps> = ({
    data,
    targetSystolic,
    targetDiastolic,
    isLoading,
}) => {
    const chart = useMemo(() => {
        const values: number[] = [];
        for (const m of data) {
            if (m.systolic !== null) values.push(m.systolic);
            if (m.diastolic !== null) values.push(m.diastolic);
        }
        if (targetSystolic) values.push(targetSystolic);
        if (targetDiastolic) values.push(targetDiastolic);

        const yMin = Math.floor((Math.min(60, ...values) - 5) / 10) * 10;
        const yMax = Math.ceil((Math.max(160, ...values) + 5) / 10) * 10;
        const innerW = WIDTH - PAD.left - PAD.right;
        const innerH = HEIGHT - PAD.top - PAD.bottom;

        const x = (i: number) => (data.length === 1 ? PAD.left + innerW / 2 : PAD.left + (innerW * i) / (data.length - 1));
        const y = (v: number) => PAD.top + innerH * (1 - (v - yMin) / (yMax - yMin));

        const systolic = data.map((m, i) => (m.systolic === null ? null : { x: x(i), y: y(m.systolic) }));
        const diastolic = data.map((m, i) => (m.diastolic === null ? null : { x: x(i), y: y(m.diastolic) }));
        const ticks: number[] = [];
        for (let v = yMin; v <= yMax; v += 20) ticks.push(v);

        return { x, y, systolic, diastolic, ticks, innerW };
    }, [data, targetSystolic, targetDiastolic]);

    if (data.length === 0) {
        return (
            <div className={styles.empty}>
                {isLoading
                    ? 'Загрузка графика...'
                    : 'График появится после первого замера. Отправьте давление в чат или добавьте замер кнопкой ниже.'}
            </div>
        );
    }

    const labelIndexes = Array.from(new Set([0, Math.floor((data.length - 1) / 2), data.length - 1]));
    const last = data[data.length - 1];

    return (
        <div className={styles.wrapper}>
            <svg
                className={styles.svg}
                viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                role="img"
                aria-label="График артериального давления"
            >
                {chart.ticks.map((tick) => (
                    <g key={tick}>
                        <line x1={PAD.left} x2={WIDTH - PAD.right} y1={chart.y(tick)} y2={chart.y(tick)} className={styles.grid} />
                        <text x={PAD.left - 8} y={chart.y(tick) + 4} className={styles.axisLabel} textAnchor="end">
                            {tick}
                        </text>
                    </g>
                ))}

                {targetSystolic ? (
                    <line
                        x1={PAD.left}
                        x2={WIDTH - PAD.right}
                        y1={chart.y(targetSystolic)}
                        y2={chart.y(targetSystolic)}
                        stroke={SYSTOLIC_COLOR}
                        className={styles.target}
                    />
                ) : null}
                {targetDiastolic ? (
                    <line
                        x1={PAD.left}
                        x2={WIDTH - PAD.right}
                        y1={chart.y(targetDiastolic)}
                        y2={chart.y(targetDiastolic)}
                        stroke={DIASTOLIC_COLOR}
                        className={styles.target}
                    />
                ) : null}

                <path d={linePath(chart.systolic)} stroke={SYSTOLIC_COLOR} className={styles.line} />
                <path d={linePath(chart.diastolic)} stroke={DIASTOLIC_COLOR} className={styles.line} />

                {data.map((m, i) => {
                    const isLast = i === data.length - 1;
                    const title = `${formatChartTime(m.timestamp)}: ${m.systolic ?? '—'}/${m.diastolic ?? '—'}, пульс ${m.pulse ?? '—'}`;
                    return (
                        <g key={m.id}>
                            {m.systolic !== null && (
                                <circle
                                    cx={chart.x(i)}
                                    cy={chart.y(m.systolic)}
                                    r={isLast ? 6 : 4}
                                    fill={RISK_COLOR[m.risk_status]}
                                    className={isLast ? styles.pointLatest : styles.point}
                                >
                                    <title>{title}</title>
                                </circle>
                            )}
                            {m.diastolic !== null && (
                                <circle
                                    cx={chart.x(i)}
                                    cy={chart.y(m.diastolic)}
                                    r={isLast ? 6 : 4}
                                    fill={RISK_COLOR[m.risk_status]}
                                    className={isLast ? styles.pointLatest : styles.point}
                                >
                                    <title>{title}</title>
                                </circle>
                            )}
                        </g>
                    );
                })}

                {labelIndexes.map((i) => (
                    <text
                        key={`x-${i}`}
                        x={chart.x(i)}
                        y={HEIGHT - 10}
                        className={styles.axisLabel}
                        textAnchor={i === 0 && data.length > 1 ? 'start' : i === data.length - 1 && data.length > 1 ? 'end' : 'middle'}
                    >
                        {formatChartTime(data[i].timestamp)}
                    </text>
                ))}
            </svg>

            <div className={styles.legend}>
                <span>
                    <i style={{ background: SYSTOLIC_COLOR }} /> Верхнее (САД)
                </span>
                <span>
                    <i style={{ background: DIASTOLIC_COLOR }} /> Нижнее (ДАД)
                </span>
                <span className={styles.legendNote}>Точки: зеленая - норма, оранжевая - выше цели, красная - риск. Пунктир - целевые значения.</span>
            </div>
            <div className={styles.lastLine}>
                Последний замер {formatChartTime(last.timestamp)}: {last.systolic ?? '—'}/{last.diastolic ?? '—'}
                {last.pulse !== null ? `, пульс ${last.pulse}` : ''}
            </div>
        </div>
    );
};
