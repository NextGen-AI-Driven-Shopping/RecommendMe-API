export interface ProductCard {
  title: string;
  price?: string;
  url: string;
  image_url?: string;
  source?: string;
  rating?: number;
  reviews?: number;
  explanation?: string;
  label?: string;
}

export interface CategoryResult {
  category: string;
  products: ProductCard[];
}

export interface ConversationMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatSession {
  id: string;
  title: string;
  sessionId: string;
  createdAt: string;
  updatedAt: string;
  conversationHistory: ConversationMessage[];
  recommendations: CategoryResult[] | null;
  activeQuery: string | null;
  clarificationQuestions: string[] | null;
  clarificationAnswers: ClarificationAnswer[];
  clarificationStep: number;
  summary: string | null;
  error: string | null;
  isLoading: boolean;
}

export interface ClarificationAnswer {
  question: string;
  answer: string;
}

export interface QueryRequest {
  user_message: string;
  session_id?: string;
  conversation_history?: ConversationMessage[];
  clarification?: ClarificationAnswer[];
}

export interface QueryResponse {
  status: 'recommendations' | 'clarification_needed';
  message?: string;
  questions?: string[];
  summary?: string;
  categories?: CategoryResult[];
  session_id?: string;
}

export interface HealthResponse {
  status: string;
  ollama?: string;
  redis?: string;
  openai?: string;
  gemini?: string;
  groq?: string;
  serpapi?: string;
}
