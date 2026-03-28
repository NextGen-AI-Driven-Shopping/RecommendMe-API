import { useEffect, useRef } from 'react';
import { Loader2, SendHorizontal } from 'lucide-react';
import { api } from '@/services/api';
import { useRecommendation } from '@/context/RecommendationContext';
import type { QueryResponse } from '@/types';

export default function ChatInput() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const {
    currentQuery,
    setCurrentQuery,
    conversationHistory,
    sessionId,
    isLoading,
    setIsLoading,
    setRecommendations,
    setClarificationQuestions,
    setActiveQuery,
    setSummary,
    setError,
    addMessage,
    resetClarificationFlow,
  } = useRecommendation();

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [currentQuery]);

  const handleSubmit = async () => {
    if (!currentQuery.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const userMessage = currentQuery.trim();
      addMessage({ role: 'user', content: userMessage });
      setCurrentQuery('');

      const response = await api.query({
        user_message: userMessage,
        session_id: sessionId,
        conversation_history: conversationHistory,
      });

      handleResponse(response, userMessage);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get recommendations';
      setError(errorMessage);
      console.error('Query error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResponse = (response: QueryResponse, initialQuery: string) => {
    addMessage({ role: 'assistant', content: formatAssistantMessage(response) });

    if (response.status === 'clarification_needed') {
      setActiveQuery(initialQuery);
      setClarificationQuestions(response.questions || (response.message ? [response.message] : null));
      setRecommendations(null);
      setSummary(null);
      return;
    }

    setRecommendations(response.categories || []);
    setSummary(response.summary || null);
    resetClarificationFlow();
  };

  const onKeyDown = async (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      await handleSubmit();
    }
  };

  return (
    <div className="border-t border-white/8 bg-[#0b0f19] px-4 py-4 sm:px-6">
      <div className="mx-auto max-w-4xl">
        <div className="rounded-3xl border border-white/10 bg-slate-900/80 shadow-[0_18px_45px_rgba(0,0,0,0.35)]">
          <div className="flex items-end gap-3 px-4 py-3">
            <textarea
              ref={textareaRef}
              rows={1}
              value={currentQuery}
              onChange={(e) => setCurrentQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Send a message..."
              disabled={isLoading}
              className="max-h-[180px] min-h-[28px] flex-1 resize-none bg-transparent py-2 text-sm text-white outline-none placeholder:text-slate-500"
            />
            <button
              onClick={handleSubmit}
              disabled={isLoading || !currentQuery.trim()}
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-500 text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-700"
              aria-label="Send message"
            >
              {isLoading ? <Loader2 size={18} className="animate-spin" /> : <SendHorizontal size={18} />}
            </button>
          </div>
        </div>
        <p className="mt-2 px-2 text-xs text-slate-500">Press Enter to send, Shift + Enter for a new line.</p>
      </div>
    </div>
  );
}

function formatAssistantMessage(response: QueryResponse): string {
  if (response.status === 'clarification_needed') {
    if (response.questions?.length) return response.questions[0];
    if (response.message) return response.message;
    return 'I need a few more details before I can recommend something.';
  }

  const parts: string[] = [];
  if (response.summary) {
    parts.push(response.summary);
  } else if (response.message) {
    parts.push(response.message);
  } else {
    parts.push('I found a few recommendations for you.');
  }

  if (response.categories?.length) {
    const categoryLines = response.categories.map((category) => {
      const productLines = category.products
        .slice(0, 3)
        .map((product, index) => `${index + 1}. ${product.title}${product.price ? ` - ${product.price}` : ''}`)
        .join('\n');
      return `${category.category}:\n${productLines}`;
    });

    parts.push(categoryLines.join('\n\n'));
  }

  return parts.join('\n\n');
}
