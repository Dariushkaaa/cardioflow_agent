import React from 'react';
import { errorMessage, useBookAppointmentMutation, useGetAvailableSlotsQuery } from '@shared/api/baseApi';
import { useAppDispatch, useAppSelector } from '@shared/lib/hooks';
import { bookingClosed } from '@shared/realtime/slice';
import styles from './SlotBookingModal.module.css';

interface SlotBookingModalProps {
    patientId: string;
}

// Причины эскалации, которые присылает бэкенд в событии show_appointment_slots
function reasonText(reason: string | null): string {
    if (!reason) return 'Рекомендуем записаться к врачу для консультации.';
    const parts: string[] = [];
    if (reason.includes('critical_blood_pressure')) parts.push('Зафиксировано критическое давление.');
    else if (reason.includes('elevated_blood_pressure')) parts.push('Давление выше целевого.');
    if (reason.includes('critical_pulse')) parts.push('Зафиксирован критический пульс.');
    else if (reason.includes('elevated_pulse')) parts.push('Пульс вне нормы.');
    if (reason.includes('side_effects')) parts.push('Вы сообщили о побочных эффектах препарата.');
    parts.push('Рекомендуем записаться к врачу.');
    return parts.join(' ');
}

export const SlotBookingModal: React.FC<SlotBookingModalProps> = ({ patientId }) => {
    const dispatch = useAppDispatch();
    const { bookingOpen: isOpen, bookingReason } = useAppSelector((state) => state.realtime);
    const { data: slots, isLoading, isError } = useGetAvailableSlotsQuery(
        { doctorType: 'therapist', limit: 3 },
        { skip: !isOpen, refetchOnMountOrArgChange: true }
    );
    const [bookSlot, { isSuccess, isLoading: isBooking, error: bookError, reset }] = useBookAppointmentMutation();

    if (!isOpen) return null;

    const close = () => {
        reset();
        dispatch(bookingClosed());
    };

    return (
        <div className={styles.overlay}>
            <div className={styles.modal}>
                <div className={styles.alertHeader}>
                    <span className={styles.alertIcon}>⚠️</span>
                    <div>
                        <h3 className={styles.alertTitle}>Нужна консультация врача</h3>
                        <p className={styles.alertDesc}>{reasonText(bookingReason)}</p>
                    </div>
                </div>

                {isSuccess ? (
                    <div className={styles.successState}>
                        <span>✅</span>
                        <h4>Вы успешно записаны!</h4>
                        <p>Запись сохранена, свободное окно закреплено за вами.</p>
                        <button className={styles.closeBtn} onClick={close}>
                            Понятно
                        </button>
                    </div>
                ) : (
                    <div className={styles.slotsList}>
                        <div className={styles.listTitle}>Ближайшие свободные приёмы:</div>
                        {isLoading && <div>Загрузка слотов...</div>}
                        {isError && <div>Не удалось загрузить свободные окна.</div>}
                        {slots && slots.length === 0 && <div>Свободных окон пока нет.</div>}
                        {bookError !== undefined && (
                            <div style={{ color: '#EF4444', fontSize: 13 }}>
                                {errorMessage(bookError, 'Не удалось записаться')}
                            </div>
                        )}
                        {slots?.map((slot) => (
                            <div key={slot.id} className={styles.slotItem}>
                                <div>
                                    <div className={styles.slotDoctor}>{slot.doctor_name}</div>
                                    <div className={styles.slotTime}>
                                        {new Date(slot.datetime).toLocaleString('ru-RU', {
                                            day: 'numeric',
                                            month: 'long',
                                            hour: '2-digit',
                                            minute: '2-digit',
                                        })}
                                    </div>
                                </div>
                                <button
                                    className={styles.bookBtn}
                                    disabled={isBooking}
                                    onClick={() => bookSlot({ patient_id: patientId, slot_id: slot.id })}
                                >
                                    Записаться
                                </button>
                            </div>
                        ))}
                        <button className={styles.cancelLink} onClick={close}>
                            Отложить
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
