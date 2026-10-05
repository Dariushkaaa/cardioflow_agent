import React, { useEffect, useRef, useState } from 'react';
import { useStore } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import type { RootState } from '@app/store';
import { useAppDispatch, useAppSelector } from '@shared/lib/hooks';
import { realtime } from '@shared/realtime/realtime';
import { onboardingRequested, patientMessageSent } from '@shared/realtime/slice';
import styles from './ChatBox.module.css';

// Быстрый ответ агента, который ведет на страницу настроек, а не отправляется как реплика
const SETUP_TIME_REPLY = 'Перейти к настройке времени';

export const ChatBox: React.FC = () => {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const store = useStore<RootState>();
    const { messages, connected, waitingForAgent } = useAppSelector((state) => state.realtime);
    const [inputValue, setInputValue] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Первое открытие чата: агент приветствует пациента и пересказывает назначения врача
    useEffect(() => {
        // Актуальное состояние читаем из стора, а не из замыкания: так приветствие не отправится дважды (React StrictMode)
        const { onboardingRequested: asked, messages: current } = store.getState().realtime;
        if (connected && !asked && current.length === 0) {
            if (realtime.requestOnboarding(dispatch)) {
                dispatch(onboardingRequested());
            }
        }
    }, [connected, dispatch, store]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, waitingForAgent]);

    const handleSendMessage = (textToSend: string) => {
        const text = textToSend.trim();
        if (!text || !connected) return;
        if (realtime.sendMessage(text, dispatch)) {
            dispatch(patientMessageSent(text));
            setInputValue('');
        }
    };

    const handleQuickReply = (reply: string) => {
        if (reply === SETUP_TIME_REPLY) {
            navigate('/treatment');
            return;
        }
        handleSendMessage(reply);
    };

    const lastMessage = messages[messages.length - 1];
    const quickReplies = lastMessage?.sender === 'agent' ? lastMessage.quick_replies ?? [] : [];

    return (
        <div className={styles.chatContainer}>
            <div className={styles.messagesList}>
                {!connected && <div className={styles.status}>Подключение к серверу...</div>}
                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`${styles.bubble} ${
                            msg.sender === 'patient' ? styles.bubblePatient : styles.bubbleAgent
                        }`}
                    >
                        {msg.text}
                    </div>
                ))}
                {waitingForAgent && <div className={`${styles.bubble} ${styles.bubbleAgent}`}>Печатает...</div>}
                <div ref={messagesEndRef} />
            </div>

            {/* Быстрые ответы от ИИ-агента */}
            {quickReplies.length > 0 && (
                <div className={styles.quickReplies}>
                    {quickReplies.map((reply) => (
                        <button key={reply} className={styles.quickReplyBtn} onClick={() => handleQuickReply(reply)}>
                            {reply}
                        </button>
                    ))}
                </div>
            )}

            {/* Поле ввода */}
            <form
                className={styles.inputBar}
                onSubmit={(e) => {
                    e.preventDefault();
                    handleSendMessage(inputValue);
                }}
            >
                <input
                    type="text"
                    className={styles.textInput}
                    placeholder={connected ? 'Напишите сообщение...' : 'Нет соединения...'}
                    value={inputValue}
                    disabled={!connected}
                    onChange={(e) => setInputValue(e.target.value)}
                />
                <button type="submit" className={styles.sendButton} disabled={!connected}>
                    ↑
                </button>
            </form>
        </div>
    );
};
