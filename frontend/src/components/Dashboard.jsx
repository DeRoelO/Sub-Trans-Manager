import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, FileEdit, RefreshCcw, History } from 'lucide-react'

const API_BASE = '/api'

export default function Dashboard() {
  const [media, setMedia] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('series')
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
      alert("Translation started in the background.")
    } catch (err) {
      alert("Error starting translation.")
    }
  }

  const handleRestoreBackup = async (bakPath) => {
    if (!confirm("Are you sure you want to restore the backup? This will overwrite the current translation.")) return;
    try {
      await fetch(`${API_BASE}/restore_backup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bak_file: bakPath })
      })
      alert("Backup restored successfully!")
      fetchMedia()
    } catch (err) {
      alert("Error restoring backup.")
    }
  }

  const seriesMedia = media.filter(m => m.kind === 'series');
  const groupedSeries = seriesMedia.reduce((acc, item) => {
    const g = item.group || "Other";
    if (!acc[g]) acc[g] = [];
    acc[g].push(item);
    return acc;
  }, {});
  
  const filmsMedia = media.filter(m => m.kind === 'film');

  const renderCard = (item, idx) => (
    <div key={idx} className="glass-panel media-card flex-col gap-4">
      <div className="flex-col">
        <h4 style={{ fontSize: '1rem', marginBottom: '0.4rem', wordBreak: 'break-all' }}>{item.name}</h4>
        {item.subpath && <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.subpath}</div>}
      </div>
      
      <div className="flex gap-2">
        {item.has_source ? <span className="badge en">SOURCE</span> : <span className="badge none">No Source</span>}
        {item.has_target ? <span className="badge nl">{item.target_tag}</span> : <span className="badge none">No {item.target_tag}</span>}
        {item.has_bak && <span className="badge" style={{ background: '#795548', color: 'white' }}>BAK</span>}
      </div>

      <div className="flex-col gap-2 mt-4" style={{ marginTop: 'auto' }}>
        <div className="flex gap-2">
          {item.has_source && (
            <button onClick={() => handleTranslate(item.source_file)} className="w-full" style={{ padding: '0.5rem' }}>
              <Play size={14} /> Translate
            </button>
          )}
          {item.has_target && (
            <button 
              onClick={() => navigate(`/editor?file=${encodeURIComponent(item.target_file)}`)} 
              className="w-full secondary" style={{ padding: '0.5rem' }}
            >
              <FileEdit size={14} /> Edit
            </button>
          )}
        </div>
        {item.has_bak && (
          <button onClick={() => handleRestoreBackup(item.bak_file)} className="w-full danger" style={{ padding: '0.5rem', background: 'rgba(255,87,34,0.1)' }}>
            <History size={14} /> Restore (.bak)
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex-col gap-6">
      <div className="flex justify-between items-center">
        <div className="flex gap-6">
          <h2 
            onClick={() => setActiveTab('series')} 
            className="tab-header"
            style={{ opacity: activeTab === 'series' ? 1 : 0.4, borderBottom: activeTab === 'series' ? '2px solid var(--accent)' : 'none' }}
          >
            📺 TV Series
          </h2>
          <h2 
            onClick={() => setActiveTab('films')} 
            className="tab-header"
            style={{ opacity: activeTab === 'films' ? 1 : 0.4, borderBottom: activeTab === 'films' ? '2px solid var(--accent)' : 'none' }}
          >
            🍿 Movies
          </h2>
        </div>
        <button onClick={fetchMedia} className="secondary">
          <RefreshCcw size={16} /> Refresh Library
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '4rem', textAlign: 'center' }}>
          <div className="loader mb-4"></div>
          <p>Scanning library...</p>
        </div>
      ) : media.length === 0 ? (
        <div className="glass-panel" style={{ padding: '4rem', textAlign: 'center' }}>
          <p className="text-muted">No media found. Please check your path settings.</p>
        </div>
      ) : activeTab === 'series' ? (
        <div className="flex-col gap-10">
          {Object.entries(groupedSeries).map(([groupName, items]) => (
            <div key={groupName}>
              <h3 style={{ marginBottom: '1.2rem', paddingBottom: '0.6rem', borderBottom: '1px solid var(--card-border)', color: 'var(--text-muted)' }}>{groupName}</h3>
              <div className="media-grid">
                {items.map((item, idx) => renderCard(item, idx))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="media-grid">
          {filmsMedia.map((item, idx) => renderCard(item, idx))}
        </div>
      )}
    </div>
  )
}
