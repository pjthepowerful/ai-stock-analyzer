import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// Stale-deploy recovery (official Vite mechanism): when a hashed chunk fails to
// load because a newer deploy replaced it, Vite fires 'vite:preloadError'. Do a
// one-time cache-busting reload so the user lands on the current version instead
// of a broken/half-loaded page. Guarded so it can never loop.
window.addEventListener('vite:preloadError', () => {
  if (!sessionStorage.getItem('paula-reloaded-stale')) {
    sessionStorage.setItem('paula-reloaded-stale', '1')
    window.location.reload()
  }
})
// Clear the guard once we've loaded successfully, so future stale deploys can
// still self-heal.
window.addEventListener('load', () => {
  setTimeout(() => sessionStorage.removeItem('paula-reloaded-stale'), 5000)
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
