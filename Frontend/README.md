# RecommendMe Frontend

A modern React frontend for the RecommendMe AI-powered product recommendation engine.

## Features

- **Smart Search**: Ask for product recommendations in natural language
- **Clarification Flow**: When queries are vague, the system asks follow-up questions
- **Conversation History**: Maintain context across multiple queries in a session
- **Beautiful UI**: Modern, responsive design using Tailwind CSS
- **Real-time Status**: Health checks and system status indicators
- **Product Cards**: Rich product displays with images, ratings, prices, and explanations

## Prerequisites

- Node.js 18+ and npm
- RecommendMe API running on http://localhost:8000

## Installation

1. Install dependencies:
```bash
npm install
```

2. Create `.env.local` file:
```bash
cp .env.example .env.local
```

Configure the API URL if your backend is running on a different host:
```
VITE_API_URL=http://localhost:8000
```

## Development

Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Build

Create a production build:
```bash
npm run build
```

Preview the production build:
```bash
npm run preview
```

## Project Structure

```
src/
├── components/          # Reusable React components
│   ├── SearchBar.tsx   # Query input and search
│   ├── ConversationView.tsx  # Chat history display
│   ├── ResultsView.tsx  # Product recommendations display
│   └── ClarificationView.tsx # Follow-up questions form
├── context/            # React Context for state management
│   └── RecommendationContext.tsx
├── pages/             # Full page components
│   └── RecommendationPage.tsx
├── services/          # API integration
│   └── api.ts
├── types/             # TypeScript interfaces
│   └── index.ts
├── App.tsx
└── main.tsx
```

## How It Works

1. **User enters a search query** via the SearchBar component
2. **API processes the query** and returns either:
   - **Recommendations**: Products organized by category with AI reasoning
   - **Clarification needed**: Follow-up questions to better understand the user's needs
3. **User answers clarification questions** (if asked)
4. **System returns personalized recommendations** based on answers
5. **Conversation history** is maintained throughout the session

## Component Details

### SearchBar
- Input field for product queries
- Real-time input state management
- Shows loading state while fetching

### ConversationView
- Displays the full conversation history
- Shows user queries and assistant responses
- Auto-scrolls to latest message
- Clear conversation button

### ResultsView
- Displays AI reasoning summary
- Shows recommendations grouped by category
- Product cards with:
  - Title and image
  - Price and source
  - Star ratings and review count
  - AI explanation of why it was recommended
  - Link to view the full product

### ClarificationView
- Shows follow-up questions
- Input fields for user answers
- Submit button to get recommendations based on answers

## API Integration

The frontend communicates with the RecommendMe API via:
- `POST /v1/query` - Submit a search query with optional conversation history
- `GET /v1/health` - Check system health and available services

See `src/services/api.ts` for full API client implementation.

## State Management

Uses React Context API (`RecommendationContext`) to manage:
- Current session ID
- Conversation history
- Current query
- Recommendations and clarification questions
- Loading and error states

## Styling

Built with Tailwind CSS with custom theme extending:
- Primary color: `#0ea5e9` (Sky Blue)
- Responsive design for mobile, tablet, desktop

## Error Handling

- API errors are caught and displayed to users
- Component-level error boundaries
- Graceful fallbacks for missing data (images, ratings, etc.)

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile responsive design

## Future Enhancements

- [ ] User authentication and saved preferences
- [ ] Search history and favorites
- [ ] Advanced filters for recommendations
- [ ] Dark mode support
- [ ] Multi-language support
- [ ] Product comparison view
- [ ] Share recommendations feature
