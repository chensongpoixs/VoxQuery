'use client';

import { useState, useRef, KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput('');
    // 重置高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // 自适应高度
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="输入您的问题，按 Enter 发送，Shift+Enter 换行..."
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none border rounded-xl px-4 py-3 text-sm
                   focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent
                   disabled:bg-gray-50 disabled:cursor-not-allowed
                   placeholder-gray-400"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !input.trim()}
        className="px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700
                   disabled:bg-gray-300 disabled:cursor-not-allowed
                   transition-colors shrink-0"
      >
        {disabled ? (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
            思考中
          </span>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        )}
      </button>
    </div>
  );
}
