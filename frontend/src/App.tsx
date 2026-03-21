import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthGuard } from '@/components/auth/auth-guard';
import { PublicRoute } from '@/components/auth/public-route';
import { AppLayout } from '@/components/layout/app-layout';
import Landing from '@/routes/landing';
import AuthCallback from '@/routes/auth-callback';
import Onboarding from '@/routes/onboarding';
import Home from '@/routes/home';
import TransactionList from '@/routes/transaction-list';
import ExpenseDetail from '@/routes/expense-detail';
import AddExpense from '@/routes/add-expense';
import Insights from '@/routes/insights';
import Limits from '@/routes/limits';
import Settings from '@/routes/settings';
import SettingsCategories from '@/routes/settings/categories';
import SettingsPaymentMethods from '@/routes/settings/payment-methods';
import SettingsTags from '@/routes/settings/tags';
import SettingsMembers from '@/routes/settings/members';
import SettingsInvite from '@/routes/settings/invite';
import SettingsTaxes from '@/routes/settings/taxes';
import JoinSpace from '@/routes/join-space';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      refetchOnWindowFocus: true,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes — no auth, no layout */}
          <Route
            path="/"
            element={
              <PublicRoute>
                <Landing />
              </PublicRoute>
            }
          />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/join/:token" element={<JoinSpace />} />

          {/* Onboarding — auth required but no space needed, no layout */}
          <Route path="/onboarding" element={<Onboarding />} />

          {/* Protected routes — auth + space required, with layout */}
          <Route
            path="/home"
            element={
              <AuthGuard>
                <AppLayout>
                  <Home />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/transactions"
            element={
              <AuthGuard>
                <AppLayout>
                  <TransactionList />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/transactions/:id"
            element={
              <AuthGuard>
                <AppLayout>
                  <ExpenseDetail />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/expenses/new"
            element={
              <AuthGuard>
                <AppLayout>
                  <AddExpense />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/insights"
            element={
              <AuthGuard>
                <AppLayout>
                  <Insights />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/limits"
            element={
              <AuthGuard>
                <AppLayout>
                  <Limits />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings"
            element={
              <AuthGuard>
                <AppLayout>
                  <Settings />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/categories"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsCategories />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/payment-methods"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsPaymentMethods />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/tags"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsTags />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/members"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsMembers />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/invite"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsInvite />
                </AppLayout>
              </AuthGuard>
            }
          />
          <Route
            path="/settings/taxes"
            element={
              <AuthGuard>
                <AppLayout>
                  <SettingsTaxes />
                </AppLayout>
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
