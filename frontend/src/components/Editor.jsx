import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Save, ArrowLeft, History } from 'lucide-react'

const API_BASE = '/api'

export default function Editor() {
  const [searchParams] = useSearchParams()
  const file_path = searchParams.get('file')
  const navigate = useNavigate()
  const [parsed, setParsed] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (file_path) {
      fetch(`${API_BASE}/srt?file_path=${encodeURIComponent(file_path)}`)
        .then(res => res.json())
        .then(data => {
          setParsed(data.parsed || [])
          setLoading(false)
        })
    }
  }, [file_path])

  const handleSave = async () => {
    setSaving(true)
    try {
      await fetch(`${API_BASE}/srt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path, parsed })
      })
      alert("Changes saved!")
    } catch (err) {
      alert("Error saving file.")
    }
    setSaving(false)
  }

  const handleTextChange = (index, newText) => {
    setParsed(prev => {
      const next = [...prev]
      const itemIdx = next.findIndex(item => item.index === index)
      if (itemIdx > -1) {
        next[itemIdx] = { ...next[itemIdx], text: newText }
      }
      return next
    })
  }

  if (loading) return <div style={{ padding: '4rem', textAlign: 'center' }}>Loading subtitle content...</div>

  return (
    <div className="flex-col gap-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <button className="secondary btn-small" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} /> Back
          </button>
          <h2>Subtitle Editor</h2>
        </div>
        <div className="flex gap-2">
           <button onClick={handleSave} disabled={saving}>
             <Save size={16} /> {saving ? 'Saving...' : 'Save Changes'}
           </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)' }}>
        <p className="text-muted" style={{ fontSize: '0.8rem' }}>
          <strong>Editing:</strong> {file_path}
        </p>
      </div>

      <div className="flex-col gap-4">
        {parsed.map((item) => (
          <div key={item.index} className="glass-panel" style={{ padding: '1.5rem', display: 'flex', gap: '1.5rem' }}>
            <div style={{ width: '120px', flexShrink: 0 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--accent)', fontWeight: 'bold', marginBottom: '0.4rem' }}>
                #{item.index}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                {item.time}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <textarea 
                value={item.text}
                onChange={(e) => handleTextChange(item.index, e.target.value)}
                style={{ 
                  width: '100%', 
                  background: 'rgba(0,0,0,0.3)', 
                  border: '1px solid var(--card-border)', 
                  color: 'white',
                  padding: '1rem',
                  borderRadius: '8px',
                  fontFamily: 'inherit',
                  fontSize: '1rem',
                  minHeight: '80px',
                  resize: 'vertical'
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end" style={{ marginTop: '2rem', paddingBottom: '4rem' }}>
         <button onClick={handleSave} disabled={saving}>
           <Save size={16} /> {saving ? 'Saving...' : 'Save Changes'}
         </button>
      </div>
    </div>
  )
}
