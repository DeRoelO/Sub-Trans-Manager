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

  const handleRestoreBackup = async (bakPath) => {
    if (!confirm("Weet je zeker dat je de backup wilt herstellen? Dit overschrijft de huidige vertaling.")) return;
    try {
      await fetch(`${API_BASE}/restore_backup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bak_file: bakPath })
      })
      alert("Backup succesvol hersteld!")
      fetchMedia()
    } catch (err) {
      alert("Fout bij herstellen backup.")
    }
  }

  const groupedMedia = media.reduce((acc, item) => {
    const g = item.group || "Overig";
    if (!acc[g]) acc[g] = [];
    acc[g].push(item);
    return acc;
  }, {});

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
        <div className="flex-col gap-8">
          {Object.entries(groupedMedia).map(([groupName, items]) => (
            <div key={groupName}>
              <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>{groupName}</h3>
              <div className="media-grid">
                {items.map((item, idx) => (
                  <div key={idx} className="glass-panel media-card flex-col gap-4">
                    <div>
                      <h4 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>{item.name}</h4>
                    </div>
                    
                    <div className="flex gap-2">
                      {item.has_en ? <span className="badge en">EN</span> : <span className="badge none">Geen EN</span>}
                      {item.has_nl ? <span className="badge nl">NL</span> : <span className="badge none">Geen NL</span>}
                      {item.has_bak && <span className="badge" style={{ background: '#795548', color: 'white' }}>BAK</span>}
                    </div>

                    <div className="flex-col gap-2 mt-4" style={{ marginTop: 'auto' }}>
                      <div className="flex gap-2">
                        {item.has_en && (
                          <button onClick={() => handleTranslate(item.en_file)} className="w-full" style={{ padding: '0.5rem' }}>
                            <Play size={14} /> Vertaal
                          </button>
                        )}
                        {item.has_nl && (
                          <button 
                            onClick={() => navigate(`/editor?file=${encodeURIComponent(item.en_file)}`)} 
                            className="w-full secondary" style={{ padding: '0.5rem' }}
                          >
                            <FileEdit size={14} /> Edit
                          </button>
                        )}
                      </div>
                      {item.has_bak && (
                        <button onClick={() => handleRestoreBackup(item.bak_file)} className="w-full danger" style={{ padding: '0.5rem', background: 'rgba(255,87,34,0.2)' }}>
                          Herstel Backup (.bak)
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
