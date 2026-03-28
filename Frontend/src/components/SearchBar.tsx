import { Loader, SendHorizontal } from 'lucide-react';
import { api } from '../services/api';
import { useRecommendation } from '../context/RecommendationContext';
import { ClarificationAnswer, QueryResponse } from '../types';

export default function SearchBar() {
  const {
    currentQuery,
    setCurrentQuery,
    conversationHistory,
    sessionId,
    isLoading,
    setIsLoading,
    setRecommendations,
    setClarificationQuestions,
    activeQuery,
    setActiveQuery,
    clarificationQuestions,
    clarificationAnswers,
    setClarificationAnswers,
    clarificationStep,
    setClarificationStep,
    setSummary,
    setError,
    addMessage,
    resetClarificationFlow,
  } = useRecommendation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!currentQuery.trim()) return;

    if (activeQuery && clarificationQuestions?.length) {
      await handleClarificationReply(currentQuery.trim());
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const userMessage = currentQuery.trim();
      addMessage({ role: 'user', content: userMessage });

      const response = await api.query({
        user_message: userMessage,
        session_id: sessionId,
        conversation_history: conversationHistory,
      });

      handleResponse(response, userMessage);
      setCurrentQuery('');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get recommendations';
      setError(errorMessage);
      console.error('Query error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClarificationReply = async (answerText: string) => {
    if (!activeQuery || !clarificationQuestions?.length) return;

    const question = clarificationQuestions[clarificationStep];
    if (!question) return;

    const nextAnswers: ClarificationAnswer[] = [
      ...clarificationAnswers,
      { question, answer: answerText },
    ];

    addMessage({ role: 'user', content: answerText });
    setCurrentQuery('');
    setClarificationAnswers(nextAnswers);

    const nextStep = clarificationStep + 1;

    if (nextStep < clarificationQuestions.length) {
      setClarificationStep(nextStep);
      addMessage({ role: 'assistant', content: clarificationQuestions[nextStep] });
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.query({
        user_message: activeQuery,
        session_id: sessionId,
        conversation_history: [
          ...conversationHistory,
          { role: 'user', content: answerText },
        ],
        clarification: nextAnswers,
      });

      handleResponse(response, activeQuery);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get recommendations';
      setError(errorMessage);
      console.error('Clarification error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResponse = (response: QueryResponse, initialQuery: string) => {
    const assistantMessage = formatAssistantMessage(response);

    addMessage({ role: 'assistant', content: assistantMessage });

    if (response.status === 'clarification_needed') {
      const questions = response.questions || [];
      setActiveQuery(initialQuery);
      setClarificationQuestions(questions);
      setClarificationAnswers([]);
      setClarificationStep(0);
      setRecommendations(null);
      setSummary(null);
      return;
    }

    setRecommendations(response.categories || []);
    setSummary(response.summary || null);
    resetClarificationFlow();
  };

  const isClarificationMode = Boolean(activeQuery && clarificationQuestions?.length);
  const promptPlaceholder = isClarificationMode
    ? 'Reply with the next detail the assistant asked for'
    : "e.g. 'Gift ideas for a 10-year-old who loves science'";

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-5">
      <div className="pointer-events-auto w-full max-w-6xl">
        <form
          onSubmit={handleSubmit}
          className="rounded-[28px] border border-white/10 bg-[#111115]/96 p-3 shadow-[0_-6px_40px_rgba(0,0,0,0.35)] backdrop-blur"
        >
          <div className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/[0.04] px-5 py-4">
            <input
              type="text"
              value={currentQuery}
              onChange={(e) => setCurrentQuery(e.target.value)}
              placeholder={promptPlaceholder}
              className="flex-1 bg-transparent text-lg text-white outline-none placeholder:text-zinc-500 sm:text-[1.35rem]"
              disabled={isLoading}
            />

            <button
              type="submit"
              disabled={isLoading || !currentQuery.trim()}
              className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.08] text-zinc-200 transition hover:bg-white/[0.14] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isLoading ? <Loader size={20} className="animate-spin" /> : <SendHorizontal size={20} />}
            </button>
          </div>

          <div className="mt-3 flex flex-col gap-2 px-2 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
            <p>Include budget, use case, or preferences for better results</p>
            <p>We don&apos;t sell products or handle transactions</p>
          </div>
        </form>
      </div>
    </div>
  );
}

function formatAssistantMessage(response: QueryResponse): string {
  if (response.status === 'clarification_needed') {
    if (response.questions?.length) {
      return response.questions[0];
    }
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
        .map((product, index) => {
          const label = product.label ? ` (${product.label})` : '';
          const price = product.price ? ` - ${product.price}` : '';
          return `${index + 1}. ${product.title}${label}${price}`;
        })
        .join('\n');

      return `${category.category}:\n${productLines}`;
    });

    parts.push(categoryLines.join('\n\n'));
  }

  return parts.join('\n\n');
}
