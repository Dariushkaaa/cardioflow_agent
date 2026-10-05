import React from 'react';
import { ChatBox } from '@widgets/chat-box/ui/ChatBox';

export const ChatPage: React.FC = () => {
    return (
        <div style={{ padding: '16px' }}>
            <h2 style={{ marginBottom: '16px' }}>Чат с ИИ-ассистентом</h2>
            <ChatBox />
        </div>
    );
};
