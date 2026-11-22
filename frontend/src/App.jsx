import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { useAuth } from './auth.jsx'
import { ToastProvider } from './toast.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import CitizenDashboard from './pages/CitizenDashboard.jsx'
import SubmitProblem from './pages/SubmitProblem.jsx'
import ProblemDetail from './pages/ProblemDetail.jsx'
import TeamsDirectory from './pages/TeamsDirectory.jsx'
import TeamDetail from './pages/TeamDetail.jsx'
import TeamDashboard from './pages/TeamDashboard.jsx'
import TeamRecommended from './pages/TeamRecommended.jsx'
import AdminDashboard from './pages/AdminDashboard.jsx'
import Profile from './pages/Profile.jsx'

function Protected({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="page-loading">Loading…</div>
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user } = useAuth()
  const home = user
    ? user.role === 'admin'
      ? '/admin'
      : user.role === 'team'
        ? '/team'
        : '/dashboard'
    : '/'
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<Layout />}>
          <Route path="/profile" element={<Protected><Profile /></Protected>} />
          <Route
            path="/dashboard"
            element={
              <Protected roles={['citizen', 'admin']}>
                <CitizenDashboard />
              </Protected>
            }
          />
          <Route
            path="/submit"
            element={
              <Protected roles={['citizen', 'admin']}>
                <SubmitProblem />
              </Protected>
            }
          />
          <Route
            path="/problem/:id"
            element={
              <Protected roles={['citizen', 'admin', 'team']}>
                <ProblemDetail />
              </Protected>
            }
          />
          <Route
            path="/teams"
            element={
              <Protected>
                <TeamsDirectory />
              </Protected>
            }
          />
          <Route
            path="/teams/:id"
            element={
              <Protected>
                <TeamDetail />
              </Protected>
            }
          />
          <Route
            path="/team"
            element={
              <Protected roles={['team', 'admin']}>
                <TeamDashboard />
              </Protected>
            }
          />
          <Route
            path="/team/recommended"
            element={
              <Protected roles={['team', 'admin']}>
                <TeamRecommended />
              </Protected>
            }
          />
          <Route
            path="/admin"
            element={
              <Protected roles={['admin']}>
                <AdminDashboard />
              </Protected>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    </ToastProvider>
  )
}
