import React from 'react';
import { Provider } from 'react-redux';
import { RouterProvider } from 'react-router-dom';
import { AuthGate } from '@features/auth-gate';
import { RealtimeBridge } from '@features/realtime-bridge';
import { PATIENT_ID } from '@shared/config';
import { SlotBookingModal } from '@widgets/slot-booking-modal';
import { router } from './routes/router';
import { store } from './store';
import './styles/global.css';

export const App: React.FC = () => (
    <Provider store={store}>
        <AuthGate>
            <RealtimeBridge />
            <RouterProvider router={router} />
            <SlotBookingModal patientId={PATIENT_ID} />
        </AuthGate>
    </Provider>
);
