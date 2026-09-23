import { AuthScreen } from '../features/auth/AuthScreen'
import { ChatScreen } from '../features/chat/ChatScreen'
import { useSession } from '../lib/auth'

export default function App() {
  const { user, isGuest, loading } = useSession()

  if (loading) return null

  if (!user && !isGuest) {
    return <AuthScreen />
  }

  return <ChatScreen />
}
