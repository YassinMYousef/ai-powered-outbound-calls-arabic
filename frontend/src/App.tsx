import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginPage from './pages/LoginPage'
import UnauthorizedPage from './pages/UnauthorizedPage'
import DashboardPage from './pages/DashboardPage'
import AgentConsolePage from './pages/AgentConsolePage'

/**
 * Role → page mapping. Purely client-side today (see auth/AuthContext.tsx) —
 * this becomes a real guard once requests carry a backend-issued token and a
 * 401/403 response, not just a locally-picked role, decides access.
 */
function RoleRouter() {
  const { user } = useAuth()

  if (!user) return <LoginPage />
  if (user.role === 'quality_manager') return <DashboardPage />
  if (user.role === 'agent') return <AgentConsolePage />
  return <UnauthorizedPage />
}

export default function App() {
  return (
    <AuthProvider>
      <RoleRouter />
    </AuthProvider>
  )
}
