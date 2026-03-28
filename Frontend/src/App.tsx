import { RecommendationProvider } from './context/RecommendationContext';
import RecommendationPage from './pages/RecommendationPage';

function App() {
  return (
    <RecommendationProvider>
      <RecommendationPage />
    </RecommendationProvider>
  );
}

export default App;
