import { useEffect, useRef } from 'react';
import { Bot, Plus, RotateCcw, UserRound } from 'lucide-react';
import { useRecommendation } from '../context/RecommendationContext';

export default function ConversationView() {
  const { conversationHistory, clearConversation } = useRecommendation();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversationHistory]);

  return (
    <div className="overflow-hidden rounded-[32px] border border-white/10 bg-[#111115] shadow-[0_20px_80px_rgba(0,0,0,0.45)]">
      <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-white/8 bg-white/[0.04] text-zinc-300">
            <Bot size={18} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">New Chat</h2>
            <p className="text-sm text-zinc-500">Natural back-and-forth product discovery</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/8 bg-white/[0.03] text-zinc-400 transition hover:bg-white/[0.07]">
            <Plus size={18} />
          </button>
          {conversationHistory.length > 0 && (
            <button
              onClick={clearConversation}
              className="inline-flex items-center gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-4 py-2 text-sm font-medium text-zinc-300 transition hover:bg-white/[0.07]"
            >
              <RotateCcw size={15} />
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="max-h-[65vh] overflow-y-auto px-6 py-8">
        <div className="mx-auto flex max-w-4xl flex-col gap-6">
          {conversationHistory.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`flex max-w-[85%] items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div
                  className={`mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-white text-black'
                      : 'border border-white/8 bg-white/[0.05] text-zinc-200'
                  }`}
                >
                  {msg.role === 'user' ? <UserRound size={16} /> : <Bot size={16} />}
                </div>
                <div
                  className={`rounded-[24px] px-5 py-4 ${
                    msg.role === 'user'
                      ? 'rounded-tr-md bg-white/[0.08] text-white'
                      : 'rounded-tl-md border border-white/8 bg-[#17171d] text-zinc-200'
                  }`}
                >
                  <p className="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-zinc-500">
                    {msg.role === 'user' ? 'You' : 'Assistant'}
                  </p>
                  <p className="whitespace-pre-wrap break-words text-[1.05rem] leading-8">{msg.content}</p>
                </div>
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>
    </div>
  );
}
