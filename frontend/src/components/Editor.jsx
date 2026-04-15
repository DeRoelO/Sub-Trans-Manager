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
  
  const scrollRef = useRef(null)

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
        <div className="glass-panel editor-container" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div className="editor-row-header" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', background: 'rgba(0,0,0,0.3)', borderBottom: '1px solid var(--card-border)', fontWeight: 'bold' }}>
             <div style={{ padding: '0.75rem 1rem' }}>Original (English)</div>
             <div style={{ padding: '0.75rem 1rem' }}>Translation (Dutch)</div>
          </div>
          <div className="editor-main-scroll" ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
            {enSrt.map((item, idx) => {
              const nlItem = nlSrt.find(n => n.index === item.index) || { text: '' }
              return (
                <div key={idx} className="editor-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '1.5rem' }}>
                  <div className="en-col">
                    <label style={{ fontSize: '0.7rem', color: 'var(--accent)', marginBottom: '0.5rem', display: 'block' }}>#{item.index} | {item.time}</label>
                    <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', fontSize: '0.95rem', border: '1px solid rgba(255,255,255,0.05)' }}>
                      {item.text}
                    </div>
                  </div>
                  <div className="nl-col">
                    <label style={{ fontSize: '0.7rem', color: 'var(--success)', marginBottom: '0.5rem', display: 'block' }}>Vertaling</label>
                    <textarea 
                      value={nlItem.text}
                      onChange={(e) => handleTextChange(item.index, e.target.value)}
                      placeholder="Typ vertaling hier..."
                      style={{ 
                        background: 'rgba(0,0,0,0.3)', 
                        border: '1px solid var(--card-border)', 
                        color: 'white', 
                        padding: '1rem', 
                        borderRadius: '8px', 
                        fontFamily: 'var(--font-body)',
                        width: '100%',
                        minHeight: '80px',
                        resize: 'vertical'
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
