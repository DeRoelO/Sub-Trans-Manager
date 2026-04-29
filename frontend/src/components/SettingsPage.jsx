import React, { useEffect, useState, useRef } from 'react'
import { Play, Square, Save, Activity, ShieldCheck, Tag, Info } from 'lucide-react'

const API_BASE = '/api'

export default function SettingsPage() {
  const [config, setConfig] = useState({})
  const [languages, setLanguages] = useState([])
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
    fetchLanguages()

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

  const fetchLanguages = async () => {
    try {
      const res = await fetch(`${API_BASE}/languages`)
      const data = await res.json()
      setLanguages(data.languages || [])
    } catch (err) {
      console.error(err)
    }
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

  const handleLanguageSelect = (langName) => {
    const lang = languages.find(l => l.name === langName)
    if (lang) {
      setConfig(prev => ({
        ...prev,
        target_language: lang.name,
        target_language_tag: lang.tag,
        target_language_variants: lang.variants
      }))
    } else {
      setConfig(prev => ({ ...prev, target_language: langName }))
    }
  }

  const handleVariantsChange = (val) => {
    const variants = val.split(',').map(v => v.trim()).filter(v => v)
    setConfig(prev => ({ ...prev, target_language_variants: variants }))
  }

  const runAuditScan = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/audit/list`)
      const data = await res.json()
      setAuditFiles(data.files || [])
    } catch (err) {
      alert("Scan failed")
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
      alert("Failed to load samples")
    }
  }

  const deleteAuditFile = async (path) => {
    if (!window.confirm("Are you sure you want to delete this translation?")) return
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
      alert("Deletion failed")
    }
  }

  const deleteSuspiciousFiles = async () => {
    const suspicious = auditFiles.filter(f => f.is_suspicious).map(f => f.path)
    if (suspicious.length === 0) {
      alert("No suspicious files found.")
      return
    }
    if (!window.confirm(`Are you sure you want to delete all ${suspicious.length} suspicious files?`)) return
    
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
        alert(`${suspicious.length} files deleted.`)
      }
    } catch (err) {
      alert("Bulk deletion failed")
    }
  }

  const runUntaggedScan = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/audit/untagged`)
      const data = await res.json()
      setUntaggedFiles(data.files || [])
    } catch (err) {
      alert("Scan failed")
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
         alert("Language could not be identified.")
         setIsIdentifying(false)
         return
      }

      if (!window.confirm(`Detected language: ${lang.toUpperCase()}. Rename to .${lang}.srt?`)) {
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
        alert("Successfully renamed!")
      }
    } catch (err) {
      alert("Error processing file.")
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
         alert("Save failed!")
      } else {
         alert("Settings saved successfully!")
      }
    } catch (err) {
      alert("Network error while saving.")
    }
  }

  const testModel = async () => {
    setTestResult("Connecting...")
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
        setTestResult("Error: " + (data.error || "Unknown error"))
        if (data.models) setAvailableModels(data.models)
      }
    } catch (err) {
      setTestResult("Network error during connection.")
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

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center' }}>Loading...</div>

  return (
    <div className="flex-col gap-8">
      <div className="flex justify-between items-center">
        <h2>System Configuration</h2>
      </div>

      <div className="flex gap-4">
        <button 
          className={activeTab === 'general' ? '' : 'secondary'} 
          onClick={() => setActiveTab('general')}
        >
          ⚙️ General Settings
        </button>
        <button 
          className={activeTab === 'audit' ? '' : 'secondary'} 
          onClick={() => setActiveTab('audit')}
        >
          🔍 Subtitle Audit Tools
        </button>
      </div>

      {activeTab === 'general' ? (
        <div className="media-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <div className="glass-panel flex-col gap-6" style={{ padding: '2rem' }}>
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck size={20} className="text-muted" />
              <h3>AI & Translation</h3>
            </div>
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
                    Connect
                  </button>
                </div>
              </div>

              {testResult && (
                <div style={{ 
                  padding: '0.75rem', 
                  background: testResult.includes('VALID') ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', 
                  border: `1px solid ${testResult.includes('VALID') ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                  borderRadius: '8px', 
                  marginBottom: '1rem', 
                  fontSize: '13px',
                  color: testResult.includes('VALID') ? 'var(--success)' : 'var(--danger)'
                }}>
                  {testResult}
                </div>
              )}
              
              <div className="form-group" style={{ opacity: availableModels.length > 0 ? 1 : 0.5 }}>
                <label>AI Model Selection</label>
                <select 
                  value={config.ai_model || ''} 
                  onChange={(e) => handleConfigChange('ai_model', e.target.value)}
                  disabled={availableModels.length === 0}
                >
                  <option value="">-- Pick a model --</option>
                  {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>

              <div className="form-group">
                <label>Target Language</label>
                <select 
                  value={config.target_language || ''} 
                  onChange={(e) => handleLanguageSelect(e.target.value)}
                >
                  <option value="">Custom / Other</option>
                  {languages.map(l => <option key={l.name} value={l.name}>{l.name}</option>)}
                </select>
                {(!languages.find(l => l.name === config.target_language)) && (
                   <input 
                     type="text" 
                     className="mt-2"
                     value={config.target_language || ''} 
                     onChange={(e) => handleConfigChange('target_language', e.target.value)}
                     placeholder="Enter language name manually..."
                   />
                )}
              </div>

              <div className="form-group">
                <div className="flex items-center gap-2">
                  <Tag size={14} />
                  <label style={{ margin: 0 }}>Language Tags & Variants</label>
                </div>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    value={config.target_language_tag || ''} 
                    onChange={(e) => handleConfigChange('target_language_tag', e.target.value)}
                    placeholder="e.g. nl"
                    style={{ width: '80px' }}
                  />
                  <input 
                    type="text" 
                    value={(config.target_language_variants || []).join(', ')} 
                    onChange={(e) => handleVariantsChange(e.target.value)}
                    placeholder="Variants (comma separated): nl, dut, dutch"
                    style={{ flex: 1 }}
                  />
                </div>
                <p className="text-muted" style={{ fontSize: '11px' }}>
                  Used to detect existing translations and prevent redundant work.
                </p>
              </div>

              <div className="divider" style={{ margin: '2rem 0', borderTop: '1px solid var(--card-border)' }} />

              <div className="flex items-center gap-2 mb-4">
                <Activity size={20} className="text-muted" />
                <h3>Paths & Scheduler</h3>
              </div>

              <div className="form-group">
                <label>Daily Auto-Start Time:</label>
                <input 
                  type="time" 
                  value={config.cron_time || ''} 
                  onChange={(e) => handleConfigChange('cron_time', e.target.value)}
                />
              </div>

              <div className="flex-col gap-2 mb-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={config.auto_identify_untagged} 
                    onChange={(e) => handleConfigChange('auto_identify_untagged', e.target.checked)}
                  />
                  <span>Auto-identify language for untagged files (.srt)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={config.auto_cleanup_suspicious} 
                    onChange={(e) => handleConfigChange('auto_cleanup_suspicious', e.target.checked)}
                  />
                  <span>Auto-delete suspicious translations (experimental)</span>
                </label>
              </div>

              <div className="media-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="form-group">
                   <label>Batch Limit</label>
                   <input 
                     type="number" 
                     value={config.batch_limit || 60} 
                     onChange={(e) => handleConfigChange('batch_limit', e.target.value)}
                   />
                </div>
                <div className="form-group">
                   <label>Delay (sec)</label>
                   <input 
                     type="number" 
                     value={config.batch_delay || 60} 
                     onChange={(e) => handleConfigChange('batch_delay', e.target.value)}
                   />
                </div>
              </div>

              <div className="form-group">
                <label>Jellyfin Webhook (Optional)</label>
                <input 
                  type="text" 
                  value={config.jellyfin_webhook || ''} 
                  onChange={(e) => handleConfigChange('jellyfin_webhook', e.target.value)}
                  placeholder="http://IP:8096/Library/Refresh?api_key=..."
                />
              </div>

              <button type="submit" className="mt-4 w-full"><Save size={16} /> Save Settings</button>
            </form>
          </div>

          <div className="flex-col gap-6">
            <div className="glass-panel" style={{ padding: '2rem' }}>
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                  <Play size={20} className="text-muted" />
                  <h3>Batch Job Control</h3>
                </div>
                {batchRunning ? (
                  <button className="danger" onClick={toggleBatch}><Square size={16} /> Stop Job</button>
                ) : (
                  <button onClick={toggleBatch}><Play size={16} /> Start Now</button>
                )}
              </div>
              <p className="text-muted" style={{ fontSize: '14px' }}>
                Manually start or stop the library scan and translation process.
              </p>
            </div>

            <div className="glass-panel" style={{ padding: '2rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Info size={20} className="text-muted" />
                  <h3>Recent Activity Logs</h3>
                </div>
                <button 
                  className="btn-small secondary" 
                  onClick={async () => {
                    await fetch(`${API_BASE}/logs/clear`, { method: 'POST' });
                    setLogs([]);
                  }}
                  style={{ padding: '4px 10px', fontSize: '11px' }}
                >
                  Clear Logs
                </button>
              </div>
              <div className="terminal" style={{ flex: 1, height: '440px' }}>
                {logs.length === 0 ? <span style={{ color: 'var(--text-muted)' }}>Waiting for activity...</span> : null}
                {logs.map((log, idx) => (
                  <div key={idx} style={{ marginBottom: '4px', borderLeft: '2px solid rgba(255,255,255,0.1)', paddingLeft: '8px' }}>{log}</div>
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
                     Suspicious Translations
                   </button>
                   <button 
                     className={auditSubTab === 'untagged' ? 'secondary btn-small' : 'btn-small ghost'} 
                     onClick={() => setAuditSubTab('untagged')}
                     style={{ fontSize: '12px', padding: '4px 12px' }}
                   >
                     Identify Untagged Files
                   </button>
                </div>
              </div>
              <div className="flex gap-2">
                {auditSubTab === 'suspicious' ? (
                  <>
                    {auditFiles.some(f => f.is_suspicious) && (
                       <button className="danger" onClick={deleteSuspiciousFiles}>🗑️ Delete All {auditFiles.filter(f => f.is_suspicious).length} Suspicious</button>
                    )}
                    <button onClick={runAuditScan}>⚡ Scan for Errors</button>
                  </>
                ) : (
                  <div className="flex gap-2">
                    <button onClick={async () => {
                      if (!window.confirm("This will identify and rename ALL untagged files in the background. Continue?")) return;
                      await fetch(`${API_BASE}/audit/rename_all`, { method: 'POST' });
                      alert("Bulk rename started. Check the logs in the General tab for progress.");
                    }} className="secondary">
                      🚀 Identify & Rename All
                    </button>
                    <button onClick={runUntaggedScan}>⚡ Scan Untagged</button>
                  </div>
                )}
              </div>
            </div>

            {auditSubTab === 'suspicious' ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)' }}>
                  {auditFiles.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }}>No files found. Run a scan to begin.</div>
                  ) : (
                    auditFiles.map((file, i) => (
                      <div 
                        key={i} 
                        onClick={() => loadAuditSample(file)}
                        style={{ 
                          padding: '1rem', 
                          borderBottom: '1px solid var(--card-border)', 
                          cursor: 'pointer',
                          background: selectedAuditFile?.path === file.path ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
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
                            ⚠️ SUSPICIOUS
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
                        <h4>Random Sample (10 lines)</h4>
                        <button className="danger" onClick={() => deleteAuditFile(selectedAuditFile.path)}>🗑️ Delete & Re-translate</button>
                      </div>
                      <div className="terminal" style={{ height: '480px', background: 'rgba(0,0,0,0.4)', padding: '1.2rem', fontSize: '13px', color: '#f8fafc' }}>
                        {auditSamples.length > 0 ? auditSamples.map((s, i) => (
                          <div key={i} style={{ marginBottom: '1.2rem' }}>
                            <div style={{ color: 'var(--accent)', fontSize: '11px', marginBottom: '4px' }}>#{s.index} — {s.time}</div>
                            <div>{s.text}</div>
                          </div>
                        )) : "Loading sample..."}
                      </div>
                    </div>
                  ) : (
                    <div style={{ height: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                      Select a file to inspect content.
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-col gap-4">
                 <p className="text-muted" style={{ fontSize: '14px' }}>
                   Files lacking language tags (e.g., <code>movie.srt</code> instead of <code>movie.en.srt</code>). 
                   Use this tool to identify the language using AI and rename the file correctly.
                 </p>
                 <div className="glass-panel" style={{ maxHeight: '600px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)' }}>
                   {untaggedFiles.length === 0 ? (
                     <div style={{ padding: '2rem', textAlign: 'center' }}>No untagged files found. Run a scan.</div>
                   ) : (
                     <table className="w-full" style={{ borderCollapse: 'collapse' }}>
                       <thead>
                         <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--card-border)' }}>
                           <th style={{ padding: '1rem' }}>Filename</th>
                           <th style={{ padding: '1rem' }}>Folder</th>
                           <th style={{ padding: '1rem' }}>Action</th>
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
                                 {isIdentifying === file.path ? 'Identifying...' : 'Detect Language'}
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
