import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConvexProvider, ConvexReactClient } from 'convex/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const convex = new ConvexReactClient(import.meta.env.VITE_CONVEX_URL || 'http://127.0.0.1:3210')
const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || ''

async function mount() {
  const rootEl = document.getElementById('root')!

  if (CLERK_KEY) {
    // Clerk + Convex: token flows to Convex via ConvexProviderWithClerk
    const { ClerkProvider, useAuth } = await import('@clerk/clerk-react')
    const { ConvexProviderWithClerk } = await import('convex/react-clerk')

    ReactDOM.createRoot(rootEl).render(
      <React.StrictMode>
        <ClerkProvider publishableKey={CLERK_KEY} afterSignInUrl="/" afterSignUpUrl="/">
          <ConvexProviderWithClerk client={convex} useAuth={useAuth}>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ConvexProviderWithClerk>
        </ClerkProvider>
      </React.StrictMode>
    )
  } else {
    // Simple-token mode: no Clerk, plain Convex provider
    ReactDOM.createRoot(rootEl).render(
      <React.StrictMode>
        <ConvexProvider client={convex}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ConvexProvider>
      </React.StrictMode>
    )
  }
}

mount()
