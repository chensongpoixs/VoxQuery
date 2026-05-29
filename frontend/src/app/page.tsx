'use client';

import { useState, useRef, useEffect } from 'react';
import ChatMessage from '@/components/Chat/ChatMessage';
import ChatInput from '@/components/Chat/ChatInput';
import VoiceRecorder from '@/components/Voice/VoiceRecorder';
import Sidebar from '@/components/Layout/Sidebar';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ text: string; score: number; source: string }>;
  isStreaming?: boolean;
}

interface Conversation {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [showVoice, setShowVoice] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const res = await fetch('/api/v1/conversations');
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch {
      // 未能加载对话列表
    }
  };

  const handleSend = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // 创建助手消息占位（流式填充）
    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const res = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          stream: true,
        }),
      });

      if (!res.ok) throw new Error('Request failed');

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let sources: any[] = [];

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.token) {
                  fullContent += data.token;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantId
                        ? { ...m, content: fullContent }
                        : m
                    )
                  );
                }
                if (data.done) {
                  sources = data.sources || [];
                  if (!conversationId && data.conv_id) {
                    setConversationId(data.conv_id);
                    loadConversations();
                  }
                }
              } catch {}
            }
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, isStreaming: false, sources }
            : m
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: '抱歉，请求失败，请稍后重试。', isStreaming: false }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceResult = async (audioBlob: Blob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');

    // 先做 ASR 识别
    try {
      const transRes = await fetch('/api/v1/voice/transcribe', {
        method: 'POST',
        body: formData,
      });
      if (transRes.ok) {
        const { text } = await transRes.json();
        if (text) {
          handleSend(text);
        }
      }
    } catch {
      // 语音识别失败
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId(null);
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      const res = await fetch(`/api/v1/conversations/${convId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(
          data.messages.map((m: any) => ({
            id: `${m.timestamp}`,
            role: m.role,
            content: m.content,
          }))
        );
        setConversationId(convId);
      }
    } catch {}
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 侧边栏 */}
      <Sidebar
        isOpen={sidebarOpen}
        conversations={conversations}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* 主区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏 */}
        <header className="bg-white border-b px-4 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1 hover:bg-gray-100 rounded"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 12h18M3 6h18M3 18h18" />
              </svg>
            </button>
            <h1 className="text-lg font-semibold text-gray-800">能源智库</h1>
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
              Beta
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowVoice(!showVoice)}
              className={`p-2 rounded-lg text-sm ${
                showVoice
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {showVoice ? '键盘输入' : '语音输入'}
            </button>
            <span className="text-xs text-gray-400">
              {conversationId ? `对话 #${conversationId.slice(0, 8)}` : '新对话'}
            </span>
          </div>
        </header>

        {/* 对话区域 */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400">
              <div className="text-6xl mb-4">⚡</div>
              <h2 className="text-xl font-semibold text-gray-600 mb-2">
                能源智库知识助手
              </h2>
              <p className="text-sm max-w-md text-center">
                我是您的能源行业知识助手，可以回答业务规范、设备手册、
                运维文档等方面的问题。请开始提问。
              </p>
              <div className="mt-6 grid grid-cols-2 gap-2 max-w-lg">
                {[
                  '变压器的日常巡检项目有哪些？',
                  '110kV变电站的安全距离要求？',
                  'SF6断路器的维护周期？',
                  '倒闸操作的标准流程？',
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="text-left text-sm p-3 bg-white border rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入区域 */}
        <div className="border-t bg-white px-4 py-3 shrink-0">
          <div className="max-w-3xl mx-auto">
            {showVoice ? (
              <VoiceRecorder
                onResult={handleVoiceResult}
                onCancel={() => setShowVoice(false)}
              />
            ) : (
              <ChatInput
                onSend={handleSend}
                disabled={isLoading}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
