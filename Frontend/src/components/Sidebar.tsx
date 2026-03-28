import { LogOut, MessageSquarePlus, Settings, Sparkles } from 'lucide-react';
import { useRecommendation } from '@/context/RecommendationContext';

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const { chatSessions, currentChatId, createNewChat, selectChat } = useRecommendation();

  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-black/60 transition lg:hidden ${
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-white/10 bg-[#020617] transition-transform lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="border-b border-white/10 px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#111827] text-indigo-300">
              <Sparkles size={18} />
            </div>
            <div>
              <p className="text-lg font-semibold text-white">RecommendMe</p>
              <p className="text-sm text-slate-400">AI shopping copilot</p>
            </div>
          </div>

          <button
            onClick={() => {
              createNewChat();
              onClose();
            }}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-400"
          >
            <MessageSquarePlus size={16} />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4">
          <p className="px-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            Recent Chats
          </p>

          <div className="mt-3 space-y-1">
            {chatSessions.map((chat) => {
              const isActive = chat.id === currentChatId;

              return (
                <button
                  key={chat.id}
                  onClick={() => {
                    selectChat(chat.id);
                    onClose();
                  }}
                  className={`w-full rounded-2xl px-3 py-3 text-left transition ${
                    isActive ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-900'
                  }`}
                >
                  <p className="truncate text-sm font-medium">{chat.title || 'New Chat'}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">
                    {chat.conversationHistory.at(-1)?.content || 'Start a new conversation'}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="border-t border-white/10 px-4 py-4">
          <div className="flex items-center gap-3 rounded-2xl bg-slate-900/80 px-3 py-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500 font-semibold text-white">
              A
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">Aditi</p>
              <p className="truncate text-xs text-slate-500">Workspace owner</p>
            </div>
            <button className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white">
              <Settings size={16} />
            </button>
            <button className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
