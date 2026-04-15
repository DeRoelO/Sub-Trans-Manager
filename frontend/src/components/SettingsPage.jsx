import React, { useEffect, useState, useRef } from 'react'
import { Play, Square, Save } from 'lucide-react'

const API_BASE = '/api'

export default function SettingsPage() {
  const [config, setConfig] = useState({})
  const [loading, setLoading] = useState(true)
  const [batchRunning, setBatchRunning] = useState(false)
  const [logs, setLogs] = useState([])
  const [testResult, setTestResult] = useState(null)
  const [availableModels, setAvailableModels] = useState([])
  const logEndRef = useRef(null)

  useEffect(() => {
    fetchConfig()
    checkBatchStatus()
    fetchModels()

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
      if (data.gemini_api_key) fetchModels()
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  const fetchModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/models`)
      const data = await res.json()
      setAvailableModels(data.models || [])
    } catch (err) {
      console.error(err)
    }
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
      const resp = await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          batch_limit: parseInt(config.batch_limit) || 60,
          batch_delay: parseInt(config.batch_delay) || 60
        })
      })
      if (!resp.ok) {
         alert("Fout bij opslaan! Controleer of Proxmox schrijf/UID 33 permissies toelaat voor de config directory.")
      } else {
         alert("Instellingen succesvol opgeslagen!")
      }
    } catch (err) {
      alert("Netwerkfout bij opslaan indens.")
    }
  }

  const testModel = async () => {
    setTestResult("Bezig met verbinden...")
    try {
      const resp = await fetch(`${API_BASE}/test_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: config.gemini_api_key, ai_model: config.ai_model || "gemini-1.5-flash" })
      })
      const data = await resp.json()
      if (resp.ok) {
        setTestResult(data.result)
        setAvailableModels(data.models || [])
      } else {
        setTestResult("Fout: " + (data.error || "Onbekende fout"))
        if (data.models) {
          setAvailableModels(data.models)
        }
      }
    } catch (err) {
      setTestResult("Netwerkfout tijdens verbinden.")
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
              <div className="flex gap-2">
                <input 
                  type="password" 
                  value={config.gemini_api_key || ''} 
                  onChange={(e) => handleConfigChange('gemini_api_key', e.target.value)}
                  placeholder="AIzaSy..."
                  style={{ flex: 1 }}
                />
                <button type="button" onClick={testModel} className="secondary" style={{ whiteSpace: 'nowrap' }}>
                  ⚡ Verbinding Maken
                </button>
              </div>
            </div>

            {testResult && (
              <div style={{ 
                padding: '0.75rem', 
                background: testResult.includes('gelukt') ? 'rgba(76,175,80,0.1)' : 'rgba(244,67,54,0.1)', 
                border: `1px solid ${testResult.includes('gelukt') ? 'rgba(76,175,80,0.3)' : 'rgba(244,67,54,0.3)'}`,
                borderRadius: '8px', 
                marginBottom: '1rem', 
                fontSize: '13px' 
              }}>
                {testResult}
              </div>
            )}
            
            <div className="form-group" style={{ opacity: availableModels.length > 0 ? 1 : 0.5 }}>
              <label>AI Model Selectie</label>
              <select 
                value={config.ai_model || ''} 
                onChange={(e) => handleConfigChange('ai_model', e.target.value)}
                disabled={availableModels.length === 0}
              >
                <option value="">-- Kies eerst Verbinding maken --</option>
                {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                <option value="gemini-1.5-flash">gemini-1.5-flash (Default)</option>
              </select>
              {availableModels.length === 0 && <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Klik eerst op 'Verbinding Maken' om modellen op te halen.</span>}
            </div>

            <div className="form-group">
              <label>Doeltaal</label>
              <input 
                type="text" 
                value={config.target_language || ''} 
                onChange={(e) => handleConfigChange('target_language', e.target.value)}
                placeholder="Dutch"
              />
            </div>

            {testResult && <div style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '1rem', fontSize: '13px' }}>{testResult}</div>}
            
            <button type="button" onClick={testModel} style={{ marginBottom: '1rem', background: 'rgba(255,255,255,0.1)' }}>⚡ Test Verbinding</button>

            <div className="form-group">
              <label>Dagelijks Automatisch Starten Om:</label>
              <input 
                type="time" 
                value={config.cron_time || ''} 
                onChange={(e) => handleConfigChange('cron_time', e.target.value)}
              />
              <span className="text-muted" style={{ fontSize: '12px', marginTop: '4px', display: 'block' }}>Kies op welk tijdstip de automatische translator taak start.</span>
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
                placeholder="http://IP:8096/Library/Refresh?api_key=XYZ..."
              />
              <span className="text-muted" style={{ fontSize: '12px', marginTop: '4px', display: 'block' }}>Zodra vertalingen gedaan zijn, krijgt Jellyfin via deze URL meteen een prikkel om z'n bibliotheek te her-indexeren, mocht je dat willen.</span>
            </div>

            <button type="submit" className="mt-4"><Save size={16} /> Opslaan in Config</button>
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
