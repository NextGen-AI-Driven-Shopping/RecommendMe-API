import { useState } from 'react';
import { HelpCircle, Loader, Send } from 'lucide-react';
import { api } from '../services/api';
import { useRecommendation } from '../context/RecommendationContext';

interface ClarificationViewProps {
  questions: string[];
}

export default function ClarificationView({ questions }: ClarificationViewProps) {
  const {
    currentQuery,
    conversationHistory,
    sessionId,
    isLoading,
    setIsLoading,
    setRecommendations,
    setClarificationQuestions,
    setSummary,
    setError,
    addMessage,
  } = useRecommendation();

  const [answers, setAnswers] = useState<Record<number, string>>({});

  const handleAnswerChange = (index: number, value: string) => {
    setAnswers(prev => ({ ...prev, [index]: value }));
  };

  const handleSubmitAnswers = async () => {
    const allAnswered = questions.every((_, idx) => answers[idx]?.trim());
    if (!allAnswered) {
      setError('Please answer all questions');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const clarificationAnswers = questions.map((q, idx) => ({
        question: q,
        answer: answers[idx],
      }));

      const answerSummary = clarificationAnswers
        .map(ca => `Q: ${ca.question}\nA: ${ca.answer}`)
        .join('\n\n');

      addMessage({ role: 'user', content: answerSummary });

      const response = await api.query({
        user_message: currentQuery || 'Based on my answers above',
        session_id: sessionId,
        conversation_history: conversationHistory,
        clarification: clarificationAnswers,
      });

      addMessage({ role: 'assistant', content: 'Here are your personalized recommendations' });

      if (response.status === 'clarification_needed') {
        setClarificationQuestions(response.questions || []);
        setRecommendations(null);
      } else {
        setRecommendations(response.categories || []);
        setSummary(response.summary || null);
        setClarificationQuestions(null);
      }

      setAnswers({});
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get recommendations';
      setError(errorMessage);
      console.error('Clarification error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-[28px] border border-white/80 bg-white/85 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
      <div className="flex items-start gap-3 border-b border-amber-200 bg-[linear-gradient(135deg,rgba(254,243,199,0.8),rgba(255,237,213,0.95))] px-6 py-5">
        <div className="rounded-2xl bg-white/80 p-3 text-amber-700 ring-1 ring-amber-200">
          <HelpCircle size={22} />
        </div>
        <div>
          <h2 className="text-xl font-semibold text-amber-950">Help us narrow the shortlist</h2>
          <p className="mt-1 text-sm leading-6 text-amber-900">
            A few quick answers will let the assistant produce more relevant recommendations.
          </p>
        </div>
      </div>

      <div className="space-y-6 p-6">
        {questions.map((question, idx) => (
          <div key={idx}>
            <label className="mb-2 block text-sm font-semibold text-slate-700">
              {idx + 1}. {question}
            </label>
            <input
              type="text"
              value={answers[idx] || ''}
              onChange={(e) => handleAnswerChange(idx, e.target.value)}
              placeholder="Your answer..."
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-amber-400 focus:bg-white focus:ring-4 focus:ring-amber-100"
              disabled={isLoading}
            />
          </div>
        ))}

        <button
          onClick={handleSubmitAnswers}
          disabled={isLoading || !questions.every((_, idx) => answers[idx]?.trim())}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-amber-500 py-3 text-sm font-semibold text-white transition hover:bg-amber-600 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isLoading ? (
            <>
              <Loader size={20} className="animate-spin" />
              <span>Finding recommendations...</span>
            </>
          ) : (
            <>
              <Send size={20} />
              <span>Get Recommendations</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
