import { useEffect, useRef } from 'react';
import { Menu, Sparkles } from 'lucide-react';
import { useRecommendation } from '@/context/RecommendationContext';
import EmptyState from './EmptyState';
import MessageBubble from './MessageBubble';
import ResultsView from './ResultsView';

interface ChatWindowProps {
  onOpenSidebar: () => void;
}

export default function ChatWindow({ onOpenSidebar }: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const { conversationHistory, recommendations, isLoading, setCurrentQuery } = useRecommendation();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversationHistory, recommendations, isLoading]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[#0b0f19]">
      <header className="flex items-center justify-between border-b border-white/8 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenSidebar}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/8 bg-white/[0.03] text-slate-300 lg:hidden"
          >
            <Menu size={18} />
          </button>
          <div className="flex items-center gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-300">
              <Sparkles size={18} />
            </div>
            <div>
              <p className="text-lg font-semibold text-white">New Chat</p>
              <p className="text-sm text-slate-500">Ask, refine, and compare in one thread</p>
            </div>
          </div>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        {conversationHistory.length === 0 ? (
          <EmptyState onSelectPrompt={setCurrentQuery} />
        ) : (
          <div className="mx-auto max-w-4xl space-y-6">
            {conversationHistory.map((message, index) => (
              <MessageBubble
                key={`${message.role}-${index}-${message.content.slice(0, 16)}`}
                message={message}
              />
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="rounded-3xl rounded-bl-md bg-slate-900/80 px-4 py-3 ring-1 ring-white/6">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
                  </div>
                </div>
              </div>
            )}

            {recommendations && <ResultsView />}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
}
