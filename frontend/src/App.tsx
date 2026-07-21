import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginPage from './pages/LoginPage'
import UnauthorizedPage from './pages/UnauthorizedPage'
import DashboardPage from './pages/DashboardPage'
import AgentConsolePage from './pages/AgentConsolePage'

/**
 * Role → page mapping. The role comes from the backend-issued JWT (see
 * auth/AuthContext.tsx); every data request carries that token, so the backend's
 * 401/403 is the real access guard and this only decides which page to render.
 */
function RoleRouter() {
  const { user, status } = useAuth()

  if (status === 'loading') return null // restoring a persisted session
  if (!user) return <LoginPage />
  // admin outranks quality_manager, so it lands on the same dashboard.
  if (user.role === 'quality_manager' || user.role === 'admin') return <DashboardPage />
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
