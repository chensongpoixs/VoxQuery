'use client';

interface Conversation {
  id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

interface SidebarProps {
  isOpen: boolean;
  conversations: Conversation[];
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onToggle: () => void;
}

export default function Sidebar({
  isOpen,
  conversations,
  onNewChat,
  onSelectConversation,
  onToggle,
}: SidebarProps) {
  if (!isOpen) return null;

  return (
    <div className="w-64 bg-white border-r flex flex-col shrink-0">
      {/* 新建对话 */}
      <div className="p-3 border-b">
        <button
          onClick={onNewChat}
          className="w-full py-2 px-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                     text-sm font-medium transition-colors flex items-center justify-center gap-2"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          新对话
        </button>
      </div>

      {/* 对话列表 */}
      <div className="flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-8">
            暂无历史对话
          </p>
        ) : (
          conversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => onSelectConversation(conv.id)}
              className="w-full text-left p-3 rounded-lg hover:bg-gray-50 mb-1 transition-colors"
            >
              <p className="text-sm text-gray-700 truncate">
                {conv.title || `对话 ${conv.id.slice(0, 8)}`}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {conv.message_count} 条消息
              </p>
            </button>
          ))
        )}
      </div>

      {/* 底部信息 */}
      <div className="p-3 border-t text-xs text-gray-400">
        <p>智能知识库 v1.0</p>
        <p>私有化部署</p>
      </div>
    </div>
  );
}
