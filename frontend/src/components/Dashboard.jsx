import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, FileEdit, RefreshCcw } from 'lucide-react'

// Use relative path since backend serves frontend
const API_BASE = '/api'

export default function Dashboard() {
  const [media, setMedia] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const fetchMedia = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/media`)
      const data = await res.json()
      setMedia(data.media || [])
    } catch (err) {
      console.error(err)
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchMedia()
  }, [])

  const handleTranslate = async (filePath) => {
    try {
      await fetch(`${API_BASE}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath })
      })
      alert("Vertaling is gestart op de achtergrond.")
    } catch (err) {
      alert("Fout bij starten vertaling.")
    }
  }

  return (
    <div className="flex-col gap-4">
      <div className="flex justify-between items-center mb-4">
        <h2>Media Bibliotheek</h2>
        <button onClick={fetchMedia} className="secondary">
          <RefreshCcw size={16} /> Verversen
        </button>
      </div>

      {loading ? (
        <p>Laden...</p>
      ) : media.length === 0 ? (
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
          <p className="text-muted">Geen items gevonden. Controleer of de paden correct zijn ingesteld.</p>
        </div>
      ) : (
        <div className="media-grid">
          {media.map((item, idx) => (
            <div key={idx} className="glass-panel media-card flex-col gap-4">
              <div>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>{item.name}</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{item.kind.toUpperCase()}</span>
              </div>
              
              <div className="flex gap-2">
                {item.has_en ? <span className="badge en">EN SRT</span> : <span className="badge none">Geen EN</span>}
                {item.has_nl ? <span className="badge nl">NL SRT</span> : <span className="badge none">Geen NL</span>}
              </div>

              <div className="flex gap-2 mt-4" style={{ marginTop: 'auto' }}>
                {item.has_en && !item.has_nl && (
                  <button onClick={() => handleTranslate(item.en_file)} className="w-full">
                    <Play size={16} /> Vertaal Nu
                  </button>
                )}
                {item.has_nl && (
                  <button 
                    onClick={() => navigate(`/editor?file=${encodeURIComponent(item.en_file)}`)} 
                    className="w-full secondary"
                  >
                    <FileEdit size={16} /> Editor
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
