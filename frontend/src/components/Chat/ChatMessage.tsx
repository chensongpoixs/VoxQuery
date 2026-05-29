'use client';

import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ text: string; score: number; source: string }>;
  isStreaming?: boolean;
}

export default function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 mb-4 ${isUser ? 'justify-end' : ''}`}>
      {/* 头像 */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
          AI
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? 'order-first' : ''}`}>
        {/* 消息气泡 */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-md'
              : 'bg-white border border-gray-200 rounded-bl-md shadow-sm'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className={`markdown-body text-sm ${message.isStreaming ? 'cursor-blink' : ''}`}>
              <ReactMarkdown>{message.content || (message.isStreaming ? '' : '...')}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* 参考来源 */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-xs text-gray-400 font-medium">参考来源:</p>
            {message.sources.map((s, i) => (
              <div
                key={i}
                className="text-xs bg-gray-50 border rounded px-2 py-1 text-gray-500"
              >
                <span className="text-blue-500 font-medium">
                  {(s.score * 100).toFixed(0)}%
                </span>
                {' '}{s.source || s.text.slice(0, 80)}...
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white text-sm font-bold shrink-0">
          U
        </div>
      )}
    </div>
  );
}
