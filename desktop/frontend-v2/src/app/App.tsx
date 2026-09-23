import { AuthScreen } from '../features/auth/AuthScreen'
import { useSession } from '../lib/auth'
import { Shell } from './Shell'

export default function App() {
  const { user, isGuest, loading } = useSession()

  if (loading) return null

  if (!user && !isGuest) {
    return <AuthScreen />
  }

  return <Shell />
}
