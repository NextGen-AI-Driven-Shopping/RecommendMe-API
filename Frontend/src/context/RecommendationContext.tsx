import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ClarificationAnswer, ConversationMessage, CategoryResult, ChatSession } from '../types';

interface RecommendationContextType {
  chatSessions: ChatSession[];
  currentChatId: string;
  currentChat: ChatSession;
  currentQuery: string;
  sessionId: string;
  conversationHistory: ConversationMessage[];
  isLoading: boolean;
  recommendations: CategoryResult[] | null;
  activeQuery: string | null;
  clarificationQuestions: string[] | null;
  clarificationAnswers: ClarificationAnswer[];
  clarificationStep: number;
  summary: string | null;
  error: string | null;

  setCurrentQuery: (query: string) => void;
  addMessage: (message: ConversationMessage) => void;
  setSessionId: (id: string) => void;
  setRecommendations: (recs: CategoryResult[] | null) => void;
  setClarificationQuestions: (questions: string[] | null) => void;
  setActiveQuery: (query: string | null) => void;
  setClarificationAnswers: (answers: ClarificationAnswer[]) => void;
  setClarificationStep: (step: number) => void;
  setSummary: (summary: string | null) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  resetClarificationFlow: () => void;
  clearConversation: () => void;
  createNewChat: () => void;
  selectChat: (chatId: string) => void;
}

const STORAGE_KEY = 'recommendme.chat.sessions';
const ACTIVE_KEY = 'recommendme.chat.active';

const RecommendationContext = createContext<RecommendationContextType | undefined>(undefined);

function createEmptyChat(title = 'New Chat'): ChatSession {
  const now = new Date().toISOString();
  return {
    id: `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    title,
    sessionId: `session_${Date.now()}`,
    createdAt: now,
    updatedAt: now,
    conversationHistory: [],
    recommendations: null,
    activeQuery: null,
    clarificationQuestions: null,
    clarificationAnswers: [],
    clarificationStep: 0,
    summary: null,
    error: null,
    isLoading: false,
  };
}

function loadPersistedSessions(): { sessions: ChatSession[]; activeId: string } {
  if (typeof window === 'undefined') {
    const initialChat = createEmptyChat();
    return { sessions: [initialChat], activeId: initialChat.id };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const activeId = window.localStorage.getItem(ACTIVE_KEY);

    if (raw) {
      const parsed = JSON.parse(raw) as ChatSession[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        const normalized = parsed.map((chat) => ({
          ...createEmptyChat(chat.title),
          ...chat,
          isLoading: false,
          error: chat.error ?? null,
        }));
        const safeActiveId =
          activeId && normalized.some((chat) => chat.id === activeId)
            ? activeId
            : normalized[0].id;
        return { sessions: normalized, activeId: safeActiveId };
      }
    }
  } catch (error) {
    console.error('Failed to load persisted chats:', error);
  }

  const initialChat = createEmptyChat();
  return { sessions: [initialChat], activeId: initialChat.id };
}

export const RecommendationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const persisted = useMemo(() => loadPersistedSessions(), []);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>(persisted.sessions);
  const [currentChatId, setCurrentChatId] = useState<string>(persisted.activeId);
  const [currentQuery, setCurrentQuery] = useState('');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(chatSessions));
  }, [chatSessions]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(ACTIVE_KEY, currentChatId);
  }, [currentChatId]);

  const updateCurrentChat = useCallback((updater: (chat: ChatSession) => ChatSession) => {
    setChatSessions((prev) =>
      prev.map((chat) =>
        chat.id === currentChatId
          ? {
              ...updater(chat),
              updatedAt: new Date().toISOString(),
            }
          : chat
      )
    );
  }, [currentChatId]);

  const currentChat =
    chatSessions.find((chat) => chat.id === currentChatId) ??
    chatSessions[0] ??
    createEmptyChat();

  const addMessage = useCallback((message: ConversationMessage) => {
    updateCurrentChat((chat) => {
      const nextTitle =
        chat.title === 'New Chat' && message.role === 'user'
          ? message.content.slice(0, 36) || 'New Chat'
          : chat.title;

      return {
        ...chat,
        title: nextTitle,
        conversationHistory: [...chat.conversationHistory, message],
      };
    });
  }, [updateCurrentChat]);

  const resetClarificationFlow = useCallback(() => {
    updateCurrentChat((chat) => ({
      ...chat,
      clarificationQuestions: null,
      clarificationAnswers: [],
      clarificationStep: 0,
      activeQuery: null,
    }));
  }, [updateCurrentChat]);

  const clearConversation = useCallback(() => {
    updateCurrentChat((chat) => ({
      ...chat,
      title: 'New Chat',
      sessionId: `session_${Date.now()}`,
      conversationHistory: [],
      recommendations: null,
      activeQuery: null,
      clarificationQuestions: null,
      clarificationAnswers: [],
      clarificationStep: 0,
      summary: null,
      error: null,
      isLoading: false,
    }));
    setCurrentQuery('');
  }, [updateCurrentChat]);

  const createNewChat = useCallback(() => {
    const next = createEmptyChat();
    setChatSessions((prev) => [next, ...prev]);
    setCurrentChatId(next.id);
    setCurrentQuery('');
  }, []);

  const selectChat = useCallback((chatId: string) => {
    setCurrentChatId(chatId);
    setCurrentQuery('');
  }, []);

  const value: RecommendationContextType = {
    chatSessions,
    currentChatId,
    currentChat,
    currentQuery,
    sessionId: currentChat.sessionId,
    conversationHistory: currentChat.conversationHistory,
    isLoading: currentChat.isLoading,
    recommendations: currentChat.recommendations,
    activeQuery: currentChat.activeQuery,
    clarificationQuestions: currentChat.clarificationQuestions,
    clarificationAnswers: currentChat.clarificationAnswers,
    clarificationStep: currentChat.clarificationStep,
    summary: currentChat.summary,
    error: currentChat.error,

    setCurrentQuery,
    addMessage,
    setSessionId: (id) => updateCurrentChat((chat) => ({ ...chat, sessionId: id })),
    setRecommendations: (recs) => updateCurrentChat((chat) => ({ ...chat, recommendations: recs })),
    setClarificationQuestions: (questions) =>
      updateCurrentChat((chat) => ({ ...chat, clarificationQuestions: questions })),
    setActiveQuery: (query) => updateCurrentChat((chat) => ({ ...chat, activeQuery: query })),
    setClarificationAnswers: (answers) =>
      updateCurrentChat((chat) => ({ ...chat, clarificationAnswers: answers })),
    setClarificationStep: (step) =>
      updateCurrentChat((chat) => ({ ...chat, clarificationStep: step })),
    setSummary: (summary) => updateCurrentChat((chat) => ({ ...chat, summary })),
    setIsLoading: (loading) => updateCurrentChat((chat) => ({ ...chat, isLoading: loading })),
    setError: (error) => updateCurrentChat((chat) => ({ ...chat, error })),
    resetClarificationFlow,
    clearConversation,
    createNewChat,
    selectChat,
  };

  return (
    <RecommendationContext.Provider value={value}>
      {children}
    </RecommendationContext.Provider>
  );
};

export const useRecommendation = () => {
  const context = useContext(RecommendationContext);
  if (!context) {
    throw new Error('useRecommendation must be used within RecommendationProvider');
  }
  return context;
};
