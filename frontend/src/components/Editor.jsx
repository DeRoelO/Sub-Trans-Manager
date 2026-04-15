import React, { useEffect, useState, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Save, ArrowLeft } from 'lucide-react'

const API_BASE = '/api'

export default function Editor() {
  const [searchParams] = useSearchParams()
  const filePathEn = searchParams.get('file')
  const filePathNl = filePathEn ? filePathEn.replace(/\.(en|eng|hi|en\.hi|eng\.hi)\.srt$/i, '.nl.srt') : null
  
  const [enSrt, setEnSrt] = useState([])
  const [nlSrt, setNlSrt] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  
  const enScrollRef = useRef(null)
  const nlScrollRef = useRef(null)
  const isSyncing = useRef(false)

  useEffect(() => {
    if (!filePathEn) return

    const loadSrts = async () => {
      setLoading(true)
      try {
        const [resEn, resNl] = await Promise.all([
          fetch(`${API_BASE}/srt?file_path=${encodeURIComponent(filePathEn)}`),
          fetch(`${API_BASE}/srt?file_path=${encodeURIComponent(filePathNl || '')}`)
        ])
        
        if (resEn.ok) {
          const data = await resEn.json()
          setEnSrt(data.parsed || [])
        }
        if (resNl.ok) {
          const data = await resNl.json()
          setNlSrt(data.parsed || [])
        }
      } catch (err) {
        console.error(err)
      }
      setLoading(false)
    }

    loadSrts()
  }, [filePathEn, filePathNl])

  const handleTextChange = (index, newText) => {
    setNlSrt(prev => prev.map(item => item.index === index ? { ...item, text: newText } : item))
  }

  const handleSave = async () => {
    try {
      await fetch(`${API_BASE}/srt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePathNl, parsed: nlSrt })
      })
      alert("Opgeslagen!")
    } catch (err) {
      alert("Fout bij opslaan.")
    }
  }

  const syncScroll = (source, target) => {
    if (isSyncing.current) return
    isSyncing.current = true
    if (target.current) {
      target.current.scrollTop = source.current.scrollTop
    }
    // Small timeout to release the lock after the passive scroll finishes
    setTimeout(() => {
      isSyncing.current = false
    }, 50)
  }

  if (!filePathEn) return <p>Geen bestand geselecteerd.</p>

  return (
    <div className="flex-col gap-4 layout" style={{ minHeight: 'auto' }}>
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate(-1)} className="secondary" style={{ padding: '0.5rem' }}>
            <ArrowLeft size={18} />
          </button>
          <h2>SRT Editor</h2>
        </div>
        <button onClick={handleSave}>
          <Save size={18} /> Opslaan
        </button>
      </div>

      {loading ? <p>Laden...</p> : (
        <div className="editor-grid">
          <div className="glass-panel editor-pane">
            <div className="editor-header">English ({filePathEn.split(/[\\/]/).pop()})</div>
            <div 
              className="editor-content" 
              ref={enScrollRef} 
              onScroll={() => syncScroll(enScrollRef, nlScrollRef)}
            >
              {enSrt.map((item, idx) => (
                <div key={idx} className="form-group" style={{ marginBottom: '0.5rem' }}>
                  <label style={{ fontSize: '0.75rem', marginBottom: '0.2rem' }}>{item.time}</label>
                  <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.9rem' }}>
                    {item.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <div className="glass-panel editor-pane">
            <div className="editor-header">Dutch ({filePathNl ? filePathNl.split(/[\\/]/).pop() : '...'})</div>
            <div 
              className="editor-content" 
              ref={nlScrollRef} 
              onScroll={() => syncScroll(nlScrollRef, enScrollRef)}
            >
              {nlSrt.map((item, idx) => (
                <div key={idx} className="form-group" style={{ marginBottom: '0.5rem' }}>
                  <label style={{ fontSize: '0.75rem', marginBottom: '0.2rem' }}>{item.time}</label>
                  <textarea 
                    value={item.text}
                    onChange={(e) => handleTextChange(item.index, e.target.value)}
                    style={{ 
                      background: 'rgba(0,0,0,0.2)', 
                      border: '1px solid var(--card-border)', 
                      color: 'white', 
                      padding: '0.75rem', 
                      borderRadius: '8px', 
                      fontFamily: 'var(--font-body)',
                      resize: 'vertical',
                      minHeight: '60px'
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
