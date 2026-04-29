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
  
  // Audit States
  const [auditFiles, setAuditFiles] = useState([])
  const [auditSamples, setAuditSamples] = useState([])
  const [selectedAuditFile, setSelectedAuditFile] = useState(null)
  const [untaggedFiles, setUntaggedFiles] = useState([])
  const [isIdentifying, setIsIdentifying] = useState(false)
  const [activeTab, setActiveTab] = useState('general') // 'general' or 'audit'
  const [auditSubTab, setAuditSubTab] = useState('suspicious') // 'suspicious' or 'untagged'
  
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

  const runAuditScan = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/audit/list`)
      const data = await res.json()
      setAuditFiles(data.files || [])
    } catch (err) {
      alert("Scan mislukt")
    }
    setLoading(false)
  }

  const loadAuditSample = async (file) => {
    setSelectedAuditFile(file)
    setAuditSamples([])
    try {
      const res = await fetch(`${API_BASE}/audit/sample?file_path=${encodeURIComponent(file.path)}`)
      const data = await res.json()
      setAuditSamples(data.samples || [])
    } catch (err) {
      alert("Sample laden mislukt")
    }
  }

  const deleteAuditFile = async (path) => {
    if (!window.confirm("Weet je zeker dat je deze vertaling wilt verwijderen?")) return
    try {
      const res = await fetch(`${API_BASE}/audit/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: path })
      })
      if (res.ok) {
        setAuditFiles(auditFiles.filter(f => f.path !== path))
        setSelectedAuditFile(null)
        setAuditSamples([])
      }
    } catch (err) {
      alert("Verwijderen mislukt")
    }
  }

  const deleteSuspiciousFiles = async () => {
    const suspicious = auditFiles.filter(f => f.is_suspicious).map(f => f.path)
    if (suspicious.length === 0) {
      alert("Geen verdachte bestanden gevonden.")
      return
    }
    if (!window.confirm(`Weet je zeker dat je alle ${suspicious.length} verdachte bestanden wilt verwijderen?`)) return
    
    try {
      const res = await fetch(`${API_BASE}/audit/delete_suspicious`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: suspicious })
      })
      if (res.ok) {
        setAuditFiles(auditFiles.filter(f => !suspicious.includes(f.path)))
        setSelectedAuditFile(null)
        setAuditSamples([])
        alert(`${suspicious.length} bestanden verwijderd.`)
      }
    } catch (err) {
      alert("Bulk verwijderen mislukt")
    }
  }

  const runUntaggedScan = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/audit/untagged`)
      const data = await res.json()
      setUntaggedFiles(data.files || [])
    } catch (err) {
      alert("Scan mislukt")
    }
    setLoading(false)
  }

  const identifyAndRename = async (file) => {
    setIsIdentifying(file.path)
    try {
      const idRes = await fetch(`${API_BASE}/audit/identify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: file.path })
      })
      const idData = await idRes.json()
      const lang = idData.language
      
      if (!lang || lang === 'unknown') {
         alert("Taal kon niet worden vastgesteld.")
         setIsIdentifying(false)
         return
      }

      if (!window.confirm(`Gedetecteerde taal: ${lang.toUpperCase()}. Hernoemen naar .${lang}.srt?`)) {
        setIsIdentifying(false)
        return
      }

      const renRes = await fetch(`${API_BASE}/audit/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: file.path, language: lang })
      })
      
      if (renRes.ok) {
        setUntaggedFiles(untaggedFiles.filter(f => f.path !== file.path))
        alert("Succesvol hernoemd!")
      }
    } catch (err) {
      alert("Fout bij verwerken.")
    }
    setIsIdentifying(false)
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
         alert("Fout bij opslaan!")
      } else {
         alert("Instellingen succesvol opgeslagen!")
      }
    } catch (err) {
      alert("Netwerkfout bij opslaan.")
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
        if (data.models) setAvailableModels(data.models)
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

  if (loading) return <div style={{ padding: '2rem' }}>Laden...</div>

  return (
    <div className="flex-col gap-6">
      <div className="flex justify-between items-center">
        <h2>Automatisering & Instellingen</h2>
      </div>

      <div className="flex gap-4">
        <button 
          className={activeTab === 'general' ? '' : 'secondary'} 
          onClick={() => setActiveTab('general')}
        >
          ⚙️ Algemene Instellingen
        </button>
        <button 
          className={activeTab === 'audit' ? '' : 'secondary'} 
          onClick={() => setActiveTab('audit')}
        >
          🔍 Subtitle Audit Tool
        </button>
      </div>

      {activeTab === 'general' ? (
        <div className="media-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div className="glass-panel flex-col gap-6" style={{ padding: '2rem' }}>
            <h3>Systeem Instellingen</h3>
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
                  background: testResult.includes('GELDIG') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', 
                  border: `1px solid ${testResult.includes('GELDIG') ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                  borderRadius: '8px', 
                  marginBottom: '1rem', 
                  fontSize: '13px',
                  color: testResult.includes('GELDIG') ? 'var(--success)' : 'var(--danger)'
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
                </select>
                {availableModels.length === 0 && <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>Klik eerst op 'Verbinding Maken' om modellen op te halen.</span>}
              </div>

              <div className="form-group">
                <label>Doeltaal</label>
                <input 
                  type="text" 
                  value={config.target_language || 'Dutch'} 
                  onChange={(e) => handleConfigChange('target_language', e.target.value)}
                  placeholder="Dutch"
                />
              </div>

              <div className="form-group">
                <label>Dagelijks Automatisch Starten Om:</label>
                <input 
                  type="time" 
                  value={config.cron_time || ''} 
                  onChange={(e) => handleConfigChange('cron_time', e.target.value)}
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
                  placeholder="http://IP:8096/Library/Refresh?api_key=XYZ..."
                />
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
              <div className="terminal" style={{ height: '400px' }}>
                {logs.length === 0 ? <span style={{ color: 'var(--text-muted)' }}>Wachten op input...</span> : null}
                {logs.map((log, idx) => (
                  <div key={idx}>{log}</div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: '2rem' }}>
            <div className="flex justify-between items-center mb-6">
              <div className="flex-col gap-1">
                <h3>Subtitle Audit Tools</h3>
                <div className="flex gap-4 mt-2">
                   <button 
                     className={auditSubTab === 'suspicious' ? 'secondary btn-small' : 'btn-small ghost'} 
                     onClick={() => setAuditSubTab('suspicious')}
                     style={{ fontSize: '12px', padding: '4px 12px' }}
                   >
                     Mogelijk Foutieve Vertalingen
                   </button>
                   <button 
                     className={auditSubTab === 'untagged' ? 'secondary btn-small' : 'btn-small ghost'} 
                     onClick={() => setAuditSubTab('untagged')}
                     style={{ fontSize: '12px', padding: '4px 12px' }}
                   >
                     Hernoem Naamloze Subtitles
                   </button>
                </div>
              </div>
              <div className="flex gap-2">
                {auditSubTab === 'suspicious' ? (
                  <>
                    {auditFiles.some(f => f.is_suspicious) && (
                       <button className="danger" onClick={deleteSuspiciousFiles}>🗑️ Verwijder alle {auditFiles.filter(f => f.is_suspicious).length} verdachte</button>
                    )}
                    <button onClick={runAuditScan}>⚡ Scan op fouten</button>
                  </>
                ) : (
                  <button onClick={runUntaggedScan}>⚡ Scan op naamloze</button>
                )}
              </div>
            </div>

            {auditSubTab === 'suspicious' ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)' }}>
                  {auditFiles.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }}>Geen bestanden gevonden. Start een scan.</div>
                  ) : (
                    auditFiles.map((file, i) => (
                      <div 
                        key={i} 
                        onClick={() => loadAuditSample(file)}
                        style={{ 
                          padding: '1rem', 
                          borderBottom: '1px solid var(--card-border)', 
                          cursor: 'pointer',
                          background: selectedAuditFile?.path === file.path ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <div>
                          <div style={{ fontSize: '14px', fontWeight: '500' }}>{file.name}</div>
                          <div className="text-muted" style={{ fontSize: '11px' }}>{file.rel_path}</div>
                        </div>
                        {file.is_suspicious && (
                          <div style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 'bold' }}>
                            ⚠️ VERDACHT
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>

                <div className="glass-panel" style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.2)' }}>
                  {selectedAuditFile ? (
                    <div className="flex-col gap-4">
                      <div className="flex justify-between items-start">
                        <h4>Steekproef (10 willekeurige regels)</h4>
                        <button className="danger" onClick={() => deleteAuditFile(selectedAuditFile.path)}>🗑️ Verwijder & Her-vertaal</button>
                      </div>
                      <div className="terminal" style={{ height: '480px', background: 'rgba(0,0,0,0.4)', padding: '1rem', fontSize: '13px', color: '#f8fafc' }}>
                        {auditSamples.length > 0 ? auditSamples.map((s, i) => (
                          <div key={i} style={{ marginBottom: '1rem' }}>
                            <div style={{ color: 'var(--accent)', fontSize: '11px' }}>#{s.index} - {s.time}</div>
                            <div>{s.text}</div>
                          </div>
                        )) : "Bezig met laden..."}
                      </div>
                    </div>
                  ) : (
                    <div style={{ height: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                      Selecteer een bestand om te controleren.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-col gap-4">
                 <p className="text-muted" style={{ fontSize: '14px' }}>
                   Sommige bestanden hebben geen taal-extensie (bijv. <code>film.srt</code> in plaats van <code>film.en.srt</code>). 
                   Gebruik deze tool om de taal te raden en het bestand correct te hernoemen.
                 </p>
                 <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)' }}>
                   {untaggedFiles.length === 0 ? (
                     <div style={{ padding: '2rem', textAlign: 'center' }}>Geen naamloze bestanden gevonden. Start een scan.</div>
                   ) : (
                     <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                       <thead>
                         <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--card-border)' }}>
                           <th style={{ padding: '1rem' }}>Bestandsnaam</th>
                           <th style={{ padding: '1rem' }}>Map</th>
                           <th style={{ padding: '1rem' }}>Actie</th>
                         </tr>
                       </thead>
                       <tbody>
                         {untaggedFiles.map((file, i) => (
                           <tr key={i} style={{ borderBottom: '1px solid var(--card-border)' }}>
                             <td style={{ padding: '1rem', fontSize: '14px' }}>{file.name}</td>
                             <td style={{ padding: '1rem', fontSize: '12px' }} className="text-muted">{file.rel_path}</td>
                             <td style={{ padding: '1rem' }}>
                               <button 
                                 className="secondary btn-small" 
                                 disabled={isIdentifying === file.path}
                                 onClick={() => identifyAndRename(file)}
                               >
                                 {isIdentifying === file.path ? 'Bezig...' : 'Taal Detecteren'}
                               </button>
                             </td>
                           </tr>
                         ))}
                       </tbody>
                     </table>
                   )}
                 </div>
              </div>
            )}
        </div>
      )}
    </div>
  )
}
