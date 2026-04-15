import React from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { Settings, Film, Clock, AlignLeft } from 'lucide-react'
import Dashboard from './components/Dashboard'
import Editor from './components/Editor'
import SettingsPage from './components/SettingsPage'
import './index.css'

function App() {
  return (
    <BrowserRouter>
      <div className="layout">
        <header className="glass-header">
          <div className="flex items-center gap-2">
            <AlignLeft style={{ color: 'var(--accent)' }} />
            <h1 style={{ fontSize: '1.5rem', margin: 0 }}>Sub-Trans Manager</h1>
          </div>
          <nav className="flex gap-4">
            <Link to="/">
              <button className="secondary">
                <Film size={18} /> Media
              </button>
            </Link>
            <Link to="/settings">
              <button className="secondary">
                <Settings size={18} /> Automatisering
              </button>
            </Link>
          </nav>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/editor" element={<Editor />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
