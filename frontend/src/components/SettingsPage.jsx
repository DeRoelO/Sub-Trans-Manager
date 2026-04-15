import React, { useEffect, useState, useRef } from 'react'
import { Play, Square, Save } from 'lucide-react'

const API_BASE = 'http://localhost:8000/api'

export default function SettingsPage() {
  const [config, setConfig] = useState({})
  const [loading, setLoading] = useState(true)
  const [batchRunning, setBatchRunning] = useState(false)
  const [logs, setLogs] = useState([])
  const logEndRef = useRef(null)

  useEffect(() => {
    fetchConfig()
    checkBatchStatus()

    const eventSource = new EventSource(`${API_BASE}/logs`)
    eventSource.onmessage = (event) => {
      if (event.data) {
        setLogs(prev => [...prev, event.data])
      }
    }

    return () => eventSource.close()
  }, [])

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/config`)
      const data = await res.json()
      setConfig(data)
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  const checkBatchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/batch`)
      const data = await res.json()
      setBatchRunning(data.is_running)
    } catch (err) {
      console.error(err)
    }
  }

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }))
  }

  const saveConfig = async (e) => {
    e.preventDefault()
    try {
      await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          batch_limit: parseInt(config.batch_limit) || 60,
          batch_delay: parseInt(config.batch_delay) || 60
        })
      })
      alert("Instellingen opgeslagen!")
    } catch (err) {
      alert("Fout bij opslaan indens.")
    }
  }

  const toggleBatch = async () => {
    try {
      const action = batchRunning ? 'stop' : 'start'
      await fetch(`${API_BASE}/batch/${action}`, { method: 'POST' })
      setBatchRunning(!batchRunning)
    } catch (err) {
      console.error(err)
    }
  }

  if (loading) return <p>Laden...</p>

  return (
    <div className="flex-col gap-4">
      <div className="flex justify-between items-center mb-4">
        <h2>Automatisering & Instellingen</h2>
      </div>

      <div className="media-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <div className="glass-panel" style={{ padding: '2rem' }}>
          <h3 className="mb-4">Instellingen</h3>
          <form onSubmit={saveConfig}>
            <div className="form-group">
              <label>Gemini API Key</label>
              <input 
                type="password" 
                value={config.gemini_api_key || ''} 
                onChange={(e) => handleConfigChange('gemini_api_key', e.target.value)}
                placeholder="AIzaSy..."
              />
            </div>
            
            <div className="form-group">
              <label>Cron Schema (APScheduler)</label>
              <input 
                type="text" 
                value={config.cron_expression || ''} 
                onChange={(e) => handleConfigChange('cron_expression', e.target.value)}
                placeholder="0 2 * * * (2 AM elke dag)"
              />
            </div>

            <div className="form-group">
               <label>Batch Limiet (aantal per run)</label>
               <input 
                 type="number" 
                 value={config.batch_limit || 60} 
                 onChange={(e) => handleConfigChange('batch_limit', e.target.value)}
               />
            </div>

            <div className="form-group">
               <label>Delay (seconden wachten na vertaling)</label>
               <input 
                 type="number" 
                 value={config.batch_delay || 60} 
                 onChange={(e) => handleConfigChange('batch_delay', e.target.value)}
               />
            </div>

            <div className="form-group">
              <label>Jellyfin Webhook (Optioneel)</label>
              <input 
                type="text" 
                value={config.jellyfin_webhook || ''} 
                onChange={(e) => handleConfigChange('jellyfin_webhook', e.target.value)}
                placeholder="http://192.168.1.50:8096/Library/Refresh..."
              />
            </div>

            <button type="submit" className="mt-4"><Save size={16} /> Opslaan</button>
          </form>
        </div>

        <div className="flex-col gap-4">
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <div className="flex justify-between items-center mb-4">
              <h3>Batch Job Controle</h3>
              {batchRunning ? (
                  <button className="danger" onClick={toggleBatch}><Square size={16} /> Stop Batch</button>
              ) : (
                  <button onClick={toggleBatch}><Play size={16} /> Start Nu</button>
              )}
            </div>
            <p className="text-muted">
              Start of stop handmatig de scan en vertaling van alle mappen conform quota en limits.
            </p>
          </div>

          <div className="glass-panel" style={{ padding: '2rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h3 className="mb-4">Batch Logs</h3>
            <div className="terminal">
              {logs.length === 0 ? <span style={{ color: 'var(--text-muted)' }}>Wachten op input...</span> : null}
              {logs.map((log, idx) => (
                <div key={idx}>{log}</div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
