import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AdminSessionProvider } from './auth/AdminSession'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AdminSessionProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AdminSessionProvider>
  </StrictMode>,
)
