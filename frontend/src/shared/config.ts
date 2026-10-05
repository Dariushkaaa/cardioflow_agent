// Демо-пациент, которого создает бэкенд при SEED_DEMO_DATA=true.
// Аутентификации пользователей в спецификации нет: JWT выдается по patient_id через /auth/token.
export const PATIENT_ID: string =
    (import.meta.env.VITE_PATIENT_ID as string | undefined) || 'd3b07384-d113-4ec6-a563-9a3d46532401';
