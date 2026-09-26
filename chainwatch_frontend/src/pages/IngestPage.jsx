/**
 * IngestPage.jsx — /ingest
 * ────────────────────────
 * Real ingestion using POST /api/v1/ingest (frozen, API-key required).
 *
 * NO fake timers. NO fake progress bars. NO fake log messages.
 * Flow: select file → submit → loading spinner → result or error.
 * The backend is synchronous — we wait for the full response.
 */
import { useState, useRef }  from 'react';
import { useNavigate }       from 'react-router-dom';
import CwNav                 from '../components/CwNav';
import { ingestLedger, clearWorkspace } from '../api/ingestion';

export default function IngestPage() {
  const navigate = useNavigate();
  const inputRef = useRef(null);

  const [file,    setFile]    = useState(null);
  const [status,  setStatus]  = useState('idle'); // 'idle' | 'loading' | 'success' | 'error'
  const [result,  setResult]  = useState(null);
  const [error,   setError]   = useState(null);
  const [clearing, setClearing] = useState(false);
  const [clearMsg, setClearMsg] = useState(null);

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (f) { setFile(f); setStatus('idle'); setResult(null); setError(null); }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f && f.name.endsWith('.csv')) {
      setFile(f); setStatus('idle'); setResult(null); setError(null);
    }
  };

  const handleSubmit = async () => {
    if (!file) return;
    setStatus('loading');
    setResult(null);
    setError(null);

    try {
      const data = await ingestLedger(file);
      setResult(data);
      setStatus('success');
    } catch (err) {
      setError(err.detail ?? err.message ?? 'Ingestion failed.');
      setStatus('error');
    }
  };

  const handleClear = async () => {
    if (!window.confirm('This will wipe the Neo4j database and all workspace state. Continue?')) return;
    setClearing(true);
    setClearMsg(null);
    try {
      const r = await clearWorkspace();
      setClearMsg(r.warnings?.length
        ? `Cleared with warnings: ${r.warnings.join('; ')}`
        : 'Workspace cleared successfully.');
    } catch (err) {
      setClearMsg(`Clear failed: ${err.detail ?? err.message}`);
    } finally {
      setClearing(false);
    }
  };

  const resultStats = result ? [
    { label: 'Dataset ID',      value: result.dataset_id?.slice(0, 12) ?? '—' },
    { label: 'Anomalies',       value: result.anomalies_found ?? 0 },
    { label: 'Peeling Chains',  value: result.peeling_chains_found ?? 0 },
    { label: 'CoinJoin Mixers', value: result.coinjoin_mixers_found ?? 0 },
    { label: 'Propagated Risk', value: result.propagated_risk_wallets ?? 0 },
    { label: 'Rows Skipped',    value: result.rows_skipped ?? 0 },
  ] : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#f8fafc' }}>
      <CwNav status="ok" />

      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 32px 48px' }}>
        <div style={{ maxWidth: 640 }}>

          <h2 style={{ fontSize: 16, fontWeight: 800, color: '#0f172a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Ingest Ledger
          </h2>
          <p style={{ fontSize: 12, color: '#64748b', marginBottom: 28, lineHeight: 1.6 }}>
            Upload a CSV ledger to run the full forensic pipeline:
            GeoIP enrichment → IsolationForest anomaly detection → SHAP attribution →
            Peeling chain + CoinJoin detection → Risk propagation → Neo4j graph persistence.
          </p>

          {/* ── Drop zone ── */}
          <div
            className={`ingest-dropzone${file ? ' has-file' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <div className="ingest-dropzone__icon">📂</div>
            {file ? (
              <>
                <div className="ingest-dropzone__file">{file.name}</div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                  {(file.size / 1024).toFixed(1)} KB · click to change
                </div>
              </>
            ) : (
              <>
                <div className="ingest-dropzone__text">Drop a CSV file here, or click to select</div>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Max 50 MB · CSV format only</div>
              </>
            )}
          </div>

          {/* ── Submit button ── */}
          <button
            onClick={handleSubmit}
            disabled={!file || status === 'loading'}
            style={{
              width: '100%',
              marginTop: 14,
              padding: '12px',
              background: !file || status === 'loading' ? '#cbd5e1' : 'var(--gov-blue)',
              color: !file || status === 'loading' ? '#94a3b8' : '#ffffff',
              border: 'none',
              borderRadius: 2,
              fontSize: 13,
              fontWeight: 800,
              cursor: !file || status === 'loading' ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
            }}
          >
            {status === 'loading' ? (
              <>
                <div className="inv-spinner" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,0.3)' }} />
                Running pipeline… this may take 5–30 seconds
              </>
            ) : (
              'Run AI Pipeline'
            )}
          </button>

          {/* ── Status messages ── */}
          {status === 'success' && result && (
            <div className="ingest-status ingest-status--success" style={{ marginTop: 14 }}>
              ✓ Analysis complete
              {result.graph_truncated && (
                <div style={{ marginTop: 4, fontSize: 11, opacity: 0.8 }}>
                  Graph display truncated to {result.graph_transaction_count} of {result.total_transaction_count} transactions.
                  Full ML analysis ran on all records.
                </div>
              )}
              {result.rows_skipped > 0 && (
                <div style={{ marginTop: 4, fontSize: 11, opacity: 0.8 }}>
                  ⚠ {result.rows_skipped} malformed row(s) skipped.
                  {result.rows_skipped_sample?.[0] && ` First: ${result.rows_skipped_sample[0]}`}
                </div>
              )}
            </div>
          )}

          {status === 'error' && (
            <div className="ingest-status ingest-status--error" style={{ marginTop: 14 }}>
              ⚠ {error}
            </div>
          )}

          {/* ── Result stats grid ── */}
          {status === 'success' && resultStats.length > 0 && (
            <>
              <div className="ingest-results" style={{ marginTop: 16 }}>
                {resultStats.map(s => (
                  <div key={s.label} className="ingest-stat">
                    <div className="ingest-stat__label">{s.label}</div>
                    <div className="ingest-stat__value">{s.value}</div>
                  </div>
                ))}
              </div>
              <button
                style={{
                  marginTop: 16,
                  padding: '10px 20px',
                  background: 'var(--gov-blue)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 2,
                  fontSize: 12,
                  fontWeight: 800,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  letterSpacing: '0.04em',
                }}
                onClick={() => navigate('/alerts')}
              >
                View Alerts →
              </button>
            </>
          )}

          {/* ── Divider ── */}
          <div style={{ margin: '32px 0 20px', borderTop: '1px solid #e2e8f0' }} />

          {/* ── Clear workspace ── */}
          <div style={{ background: '#fff', border: '1px solid #94a3b8', padding: '16px 20px', borderRadius: 2 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: '#0f172a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Clear Workspace
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 12, lineHeight: 1.6 }}>
              Wipes the Neo4j database and resets all JSON workspace state.
              This cannot be undone.
            </div>
            <button
              onClick={handleClear}
              disabled={clearing}
              style={{
                padding: '7px 14px',
                background: '#fff',
                border: '1px solid var(--gov-red)',
                color: 'var(--gov-red)',
                borderRadius: 2,
                fontSize: 11,
                fontWeight: 800,
                cursor: clearing ? 'not-allowed' : 'pointer',
                fontFamily: 'inherit',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                opacity: clearing ? 0.6 : 1,
              }}
            >
              {clearing ? 'Clearing…' : 'Wipe Database'}
            </button>
            {clearMsg && (
              <div style={{ marginTop: 8, fontSize: 11, color: clearMsg.includes('failed') ? 'var(--gov-red)' : 'var(--gov-green)' }}>
                {clearMsg}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
