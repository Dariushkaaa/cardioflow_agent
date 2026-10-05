import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@widgets/app-layout';
import { HomePage } from '@pages/home';
import { ChatPage } from '@pages/chat';
import { StatsPage } from '@pages/stats';
import { TreatmentPage } from '@pages/treatment';
import { AppointmentsPage } from '@pages/appointments';
import { RecommendationsPage } from '@pages/recommendations';

export const router = createBrowserRouter([
    {
        path: '/',
        element: <AppLayout />,
        children: [
            { index: true, element: <HomePage /> },
            { path: 'chat', element: <ChatPage /> },
            { path: 'stats', element: <StatsPage /> },
            { path: 'treatment', element: <TreatmentPage /> },
            { path: 'appointments', element: <AppointmentsPage /> },
            { path: 'recommendations', element: <RecommendationsPage /> },
        ],
    },
]);
