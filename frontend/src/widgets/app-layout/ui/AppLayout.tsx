import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAppSelector } from '@shared/lib/hooks';
import styles from './AppLayout.module.css';

const NAV_ITEMS = [
    { to: '/', label: 'Главная', icon: '🏠' },
    { to: '/chat', label: 'Чат с ИИ', icon: '💬' },
    { to: '/stats', label: 'Аналитика', icon: '📊' },
    { to: '/treatment', label: 'Лечение', icon: '💊' },
    { to: '/appointments', label: 'Запись', icon: '📅' },
];

export const AppLayout: React.FC = () => {
    const connected = useAppSelector((state) => state.realtime.connected);
    return (
        <div className={styles.container}>
            {/* Десктоп-меню */}
            <aside className={styles.sidebar}>
                <div className={styles.logo}>
                    <span>❤️</span> CardioFlow
                    <span
                        title={connected ? 'Соединение с сервером установлено' : 'Нет соединения с сервером'}
                        style={{ marginLeft: 'auto', fontSize: 12, color: connected ? '#10B981' : '#EF4444' }}
                    >
                        ●
                    </span>
                </div>
                <nav className={styles.desktopNav}>
                    {NAV_ITEMS.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
                            }
                        >
                            <span>{item.icon}</span>
                            <span>{item.label}</span>
                        </NavLink>
                    ))}
                </nav>
            </aside>

            {/* Контентная зона */}
            <div className={styles.mainWrapper}>
                <main className={styles.mainContent}>
                    <Outlet />
                </main>
            </div>

            {/* Мобильный Bottom Bar */}
            <nav className={styles.bottomNav}>
                {NAV_ITEMS.map((item) => (
                    <NavLink
                        key={item.to}
                        to={item.to}
                        className={({ isActive }) =>
                            `${styles.bottomNavItem} ${isActive ? styles.bottomNavItemActive : ''}`
                        }
                    >
                        <span style={{ fontSize: '18px' }}>{item.icon}</span>
                        <span>{item.label}</span>
                    </NavLink>
                ))}
            </nav>
        </div>
    );
};
