import { useEffect } from 'react';
import { PATIENT_ID } from '@shared/config';
import { useAppDispatch } from '@shared/lib/hooks';
import { realtime } from '@shared/realtime/realtime';

/** Держит одно WebSocket-соединение на все приложение: события попадают в Redux-стор. */
export const RealtimeBridge = (): null => {
    const dispatch = useAppDispatch();

    useEffect(() => {
        realtime.start(PATIENT_ID, dispatch);
        return () => realtime.stop();
    }, [dispatch]);

    return null;
};
