import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Landing from '@/routes/landing';
import AuthCallback from '@/routes/auth-callback';
import Onboarding from '@/routes/onboarding';
import Home from '@/routes/home';
import TransactionList from '@/routes/transaction-list';
import ExpenseDetail from '@/routes/expense-detail';
import Insights from '@/routes/insights';
import Limits from '@/routes/limits';
import Settings from '@/routes/settings';
import JoinSpace from '@/routes/join-space';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000, // 2 minutes
      refetchOnWindowFocus: true,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/home" element={<Home />} />
          <Route path="/transactions" element={<TransactionList />} />
          <Route path="/transactions/:id" element={<ExpenseDetail />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/limits" element={<Limits />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/join/:token" element={<JoinSpace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
