import React, { useState, useEffect } from 'react';
import { Play, Download, FileText, CheckCircle2, RefreshCw, BarChart2 } from 'lucide-react';

export default function ExperimentRunner() {
  const [condition, setCondition] = useState('all');
  const [sessions, setSessions] = useState(2);
  const [turns, setTurns] = useState(4);
  const [isRunning, setIsRunning] = useState(false);
  const [logsList, setLogsList] = useState([]);
  const [activeLogContent, setActiveLogContent] = useState(null);
  const [activeLogId, setActiveLogId] = useState(null);

  // Fetch list of session logs from API
  const fetchLogs = async () => {
    try {
      const res = await fetch('/api/logs');
      if (res.ok) {
        const data = await res.json();
        setLogsList(data);
      }
    } catch (e) {
      console.error('Failed to load logs', e);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleRunExperiment = async () => {
    setIsRunning(true);
    try {
      // In web app, we can trigger session runs or simulate
      const conditionsToRun = condition === 'all' ? ['A', 'B', 'C'] : [condition];
      for (const cond of conditionsToRun) {
        for (let i = 0; i < sessions; i++) {
          await fetch('/api/session/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ condition: cond }),
          });
          // Wait briefly
          await new Promise((r) => setTimeout(r, 1000));
        }
      }
      await fetchLogs();
    } catch (err) {
      console.error('Experiment run error:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleViewLog = async (sessionId) => {
    try {
      setActiveLogId(sessionId);
      const res = await fetch(`/api/logs/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveLogContent(data);
      }
    } catch (e) {
      alert('Gagal membaca log sesi');
    }
  };

  const handleExportCSV = () => {
    if (!activeLogContent || activeLogContent.length === 0) return;

    const headers = ['turn', 'persona', 'emotion', 'drift_detected', 'regenerations', 'latency_total', 'final_text'];
    const rows = activeLogContent.map((item) => [
      item.turn,
      item.persona,
      item.emotion,
      item.verdict?.drift_detected ? 'true' : 'false',
      item.regenerations || 0,
      item.latency_ms?.total || 0,
      `"${(item.final_text || '').replace(/"/g, '""')}"`,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${activeLogId}_summary.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      {/* Simulation Setup Card */}
      <div className="studio-card" style={{ marginBottom: '24px' }}>
        <div className="card-title">
          <span>Pengaturan Runner Eksperimen (FR-12)</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Simulasi Teks Otomatis A/B/C untuk Evaluasi Skripsi
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '20px' }}>
          <div className="form-group">
            <label className="form-label">Kondisi Eksperimen:</label>
            <select
              className="form-select"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              disabled={isRunning}
            >
              <option value="all">Semua Kondisi (A, B, C)</option>
              <option value="A">Kondisi A (Langsung Tanpa Supervisor)</option>
              <option value="B">Kondisi B (Re-prompt Tiap Giliran)</option>
              <option value="C">Kondisi C (Supervisor Penuh)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Jumlah Sesi per Kondisi:</label>
            <input
              type="number"
              min={1}
              max={10}
              className="form-input"
              value={sessions}
              onChange={(e) => setSessions(parseInt(e.target.value) || 1)}
              disabled={isRunning}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Jumlah Giliran per Sesi:</label>
            <input
              type="number"
              min={2}
              max={20}
              className="form-input"
              value={turns}
              onChange={(e) => setTurns(parseInt(e.target.value) || 2)}
              disabled={isRunning}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            CLI Alternatif: <code>python -m experiments.run --condition all --sessions 5 --turns 10 --export-csv ringkasan.csv</code>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleRunExperiment}
            disabled={isRunning}
          >
            {isRunning ? <RefreshCw size={16} className="spin" /> : <Play size={16} fill="currentColor" />}
            {isRunning ? 'Menjalankan Simulasi...' : 'Mulai Simulasi Eksperimen'}
          </button>
        </div>
      </div>

      {/* Logs and Results Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
        {/* Available Logs List */}
        <div className="studio-card">
          <div className="card-title">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileText size={18} />
              <span>Daftar Log Sesi</span>
            </div>
            <button
              onClick={fetchLogs}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <RefreshCw size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '500px', overflowY: 'auto' }}>
            {logsList.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                Belum ada berkas log JSONL.
              </div>
            ) : (
              logsList.map((log) => {
                const isSelected = activeLogId === log.session_id;
                return (
                  <div
                    key={log.session_id}
                    onClick={() => handleViewLog(log.session_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(0, 242, 254, 0.1)' : 'var(--bg-tertiary)',
                      border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                      fontSize: '0.825rem',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    <div style={{ color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)', fontWeight: 600 }}>
                      {log.session_id}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Ukuran: {Math.round(log.size_bytes / 1024)} KB
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Log Content Inspector */}
        <div className="studio-card">
          <div className="card-title">
            <span>Detail Log: {activeLogId || 'Pilih Sesi Log'}</span>
            {activeLogContent && (
              <button className="btn btn-secondary" onClick={handleExportCSV}>
                <Download size={14} />
                Ekspor ke CSV
              </button>
            )}
          </div>

          {activeLogContent ? (
            <div style={{ overflowX: 'auto', maxHeight: '500px' }}>
              <table className="ledger-table">
                <thead>
                  <tr>
                    <th>Giliran</th>
                    <th>Persona</th>
                    <th>Emosi</th>
                    <th>Drift?</th>
                    <th>Regen</th>
                    <th>Latensi</th>
                    <th>Teks Final</th>
                  </tr>
                </thead>
                <tbody>
                  {activeLogContent.map((row, i) => (
                    <tr key={i}>
                      <td>#{row.turn}</td>
                      <td style={{ fontWeight: 600 }}>{row.persona}</td>
                      <td>{row.emotion}</td>
                      <td>
                        {row.verdict?.drift_detected ? (
                          <span style={{ color: 'var(--accent-rose)', fontWeight: 700 }}>YA</span>
                        ) : (
                          <span style={{ color: 'var(--accent-emerald)' }}>Tidak</span>
                        )}
                      </td>
                      <td>{row.regenerations || 0}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{row.latency_ms?.total || 0}ms</td>
                      <td style={{ maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {row.final_text}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '60px' }}>
              Pilih berkas log di panel kiri untuk memeriksa giliran percakapan dan mengekspor CSV.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
