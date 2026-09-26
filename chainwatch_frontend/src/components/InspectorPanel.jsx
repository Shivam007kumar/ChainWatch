/**
 * InspectorPanel.jsx
 * ──────────────────
 * Unified right-side inspector for the investigation workstation.
 * Renders one of five panels based on the selected entity type:
 *
 *   wallet      → P4b: GET /investigations/wallet/{address}
 *   transaction → P4c: GET /investigations/transaction/{txid}
 *   ip          → P4d: GET /investigations/ip/{ip}
 *   timeline    → P4e: GET /investigations/wallet/{address}/timeline
 *   path/arc    → P4f: arc connection detail (no extra fetch needed)
 *
 * Props:
 *   selectedNode  {object|null}  — node clicked in the graph
 *   selectedLink  {object|null}  — link/arc clicked in the graph
 *   onNavigate    {function}     — (address) => navigate to /investigate/:address
 *   onClear       {function}     — clear the selection
 *   datasetId     {string|null}  — optional dataset scope
 *
 * Rules:
 *   - Only renders backend-returned data. No invented values.
 *   - All values display exactly as returned by the API.
 *   - Missing fields show "N/A" or are hidden.
 *   - PDF report opened via window.open (no new endpoint needed).
 */

import { useState, useEffect } from 'react';
import {
  getWalletSummary,
  getWalletTimeline,
  getTransactionDetail,
  getIpDetail,
} from '../api/investigations';
import { getReportUrl } from '../api/ingestion';

// ── Helpers ────────────────────────────────────────────────────────────────
function Kv({ label, value, mono = true, addr = false }) {
  if (value == null || value === '' || value === 'N/A') return null;
  return (
    <div className="inv-kv">
      <span className="inv-kv__key">{label}</span>
      <span className={addr ? 'inv-kv__val inv-kv__val--addr' : 'inv-kv__val'}
            style={mono ? {} : { fontFamily: 'var(--font)' }}>
        {String(value)}
      </span>
    </div>
  );
}

function Section({ title, children }) {
  const hasContent = Array.isArray(children)
    ? children.some(c => c != null)
    : children != null;
  if (!hasContent) return null;
  return (
    <div className="inv-section">
      <div className="inv-section__title">{title}</div>
      {children}
    </div>
  );
}

function RiskBadge({ score }) {
  const sev = score >= 90 ? 'critical' : score >= 70 ? 'high' : score >= 50 ? 'medium' : 'low';
  return <span className={`inv-risk-badge inv-risk-badge--${sev}`}>{score}%</span>;
}

function Loading() {
  return (
    <div className="inv-inspector__loading">
      <div className="inv-spinner" />
      <span>Loading…</span>
    </div>
  );
}

function ErrorMsg({ msg }) {
  return (
    <div className="inv-section">
      <div style={{ color: 'var(--gov-red)', fontSize: 11, padding: '4px 0' }}>
        ⚠ {msg}
      </div>
    </div>
  );
}

// ── Tab switcher inside the inspector ─────────────────────────────────────
function Tabs({ tabs, active, onChange }) {
  return (
    <div style={{
      display: 'flex', borderBottom: '1px solid #e2e8f0',
      padding: '0 16px', background: '#f8fafc', flexShrink: 0,
    }}>
      {tabs.map(t => (
        <button key={t.id} onClick={() => onChange(t.id)} style={{
          padding: '8px 12px', border: 'none', borderBottom: active === t.id ? '2px solid var(--gov-blue)' : '2px solid transparent',
          background: 'transparent', cursor: 'pointer', fontSize: 10,
          fontWeight: 800, color: active === t.id ? 'var(--gov-blue)' : '#64748b',
          fontFamily: 'inherit', textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── P4b: Wallet inspector ─────────────────────────────────────────────────
function WalletInspector({ address, onNavigate, datasetId }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [tab,     setTab]     = useState('summary'); // 'summary' | 'evidence' | 'shap' | 'timeline'

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    setError(null);
    getWalletSummary(address, datasetId)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.detail ?? e.message ?? 'Failed to load wallet.'); setLoading(false); });
  }, [address, datasetId]);

  if (loading) return <Loading />;
  if (error)   return <ErrorMsg msg={error} />;
  if (!data || data.error) return <ErrorMsg msg={data?.error === 'not_found' ? 'Wallet not found in Neo4j.' : (data?.error ?? 'No data.')} />;

  const entity  = data.entity  ?? {};
  const risk    = data.risk    ?? {};
  const stats   = data.statistics ?? {};
  const shap    = data.shap    ?? [];
  const ips     = data.observed_ips ?? [];
  const txids   = data.correlated_txids ?? [];

  const tabs = [
    { id: 'summary',  label: 'Summary'  },
    { id: 'evidence', label: 'Evidence' },
    { id: 'shap',     label: 'SHAP'     },
    { id: 'timeline', label: 'Timeline' },
  ];

  return (
    <>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      <div className="inv-inspector__body">

        {tab === 'summary' && <>
          <Section title="Identity">
            <Kv label="Address"  value={entity.address}    addr />
            <Kv label="State"    value={entity.state}      mono={false} />
            <Kv label="Cluster"  value={entity.cluster}    mono={false} />
            <Kv label="First Seen" value={entity.first_seen} mono={false} />
          </Section>

          <Section title="Risk Assessment">
            <div className="inv-kv">
              <span className="inv-kv__key">Risk Score</span>
              <RiskBadge score={Math.round(risk.score ?? 0)} />
            </div>
            <Kv label="Severity"  value={entity.risk_level} mono={false} />
            {(risk.factors ?? []).length > 0 && (
              <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                {(risk.factors ?? []).map((f, i) => (
                  <span key={i} className="inv-factor-tag">{f}</span>
                ))}
              </div>
            )}
          </Section>

          <Section title="Transaction Activity">
            <Kv label="TX Count"    value={stats.transaction_count} />
            <Kv label="Total Fees"  value={stats.total_fees_btc != null ? `${stats.total_fees_btc} BTC` : null} />
            <Kv label="Unique IPs"  value={stats.unique_ips} />
          </Section>

          {ips.length > 0 && (
            <Section title="Observed Network IPs">
              {ips.slice(0, 6).map((ip, i) => (
                <div key={i} className="inv-kv" style={{ alignItems: 'flex-start' }}>
                  <span className="inv-kv__key" style={{ fontFamily: 'var(--mono)', fontSize: 9 }}>{ip.ip}</span>
                  <span className="inv-kv__val" style={{ fontSize: 9, textAlign: 'right' }}>
                    {[ip.state, ip.asn].filter(Boolean).join(' · ')}
                  </span>
                </div>
              ))}
              {ips.length > 6 && (
                <div style={{ fontSize: 9, color: '#94a3b8', paddingTop: 4 }}>+{ips.length - 6} more</div>
              )}
            </Section>
          )}
        </>}

        {tab === 'evidence' && <>
          <Section title="Correlated Transactions">
            {txids.length === 0
              ? <div style={{ fontSize: 11, color: '#94a3b8' }}>No correlated transactions.</div>
              : txids.slice(0, 15).map((tid, i) => (
                  <div key={i} className="inv-kv">
                    <span className="inv-kv__key">TX {i + 1}</span>
                    <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>
                      {tid.slice(0, 24)}…
                    </span>
                  </div>
                ))
            }
          </Section>
          {(data.evidence ?? []).length > 0 && (
            <Section title="Detection Evidence">
              {(data.evidence ?? []).map((ev, i) => (
                <div key={i} style={{ padding: '6px 0', borderBottom: '1px dashed #e2e8f0', fontSize: 10 }}>
                  <div style={{ fontWeight: 800, color: '#0f172a', marginBottom: 2, textTransform: 'uppercase', fontSize: 9 }}>
                    {ev.type}
                  </div>
                  {ev.title && <div style={{ color: '#475569' }}>{ev.title}</div>}
                  {ev.confidence != null && (
                    <div style={{ color: '#64748b', marginTop: 2 }}>
                      Confidence: {Math.round(ev.confidence * 100)}%
                    </div>
                  )}
                </div>
              ))}
            </Section>
          )}
        </>}

        {tab === 'shap' && (
          <Section title="XAI Feature Attribution (SHAP)">
            {shap.length === 0
              ? <div style={{ fontSize: 11, color: '#94a3b8' }}>No SHAP data available.</div>
              : shap.map((attr, i) => (
                  <div key={i} className="inv-kv">
                    <span style={{ fontSize: 9, color: '#64748b', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {attr.label ?? attr.feature}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                      <span className={`shap-chip ${attr.direction === 'positive' ? 'shap-pos' : 'shap-neg'}`}>
                        <span className="shap-pct">{attr.direction === 'positive' ? '+' : '-'}{attr.pct_contribution}%</span>
                        <span className="shap-sigma">{Math.abs(attr.sigma ?? 0).toFixed(1)}σ</span>
                      </span>
                    </span>
                  </div>
                ))
            }
          </Section>
        )}

        {tab === 'timeline' && (
          <WalletTimeline address={address} datasetId={datasetId} />
        )}
      </div>

      <div className="inv-inspector__actions">
        <button
          className="inv-action-btn inv-action-btn--primary"
          onClick={() => onNavigate(address)}
        >
          Re-investigate
        </button>
        <button
          className="inv-action-btn"
          onClick={() => window.open(getReportUrl(address), '_blank')}
        >
          PDF Report
        </button>
      </div>
    </>
  );
}

// ── P4e: Timeline sub-panel ───────────────────────────────────────────────
function WalletTimeline({ address, datasetId }) {
  const [events,  setEvents]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    getWalletTimeline(address, datasetId, 60)
      .then(d => { setEvents(d.events ?? []); setLoading(false); })
      .catch(e => { setError(e.detail ?? e.message ?? 'Failed to load timeline.'); setLoading(false); });
  }, [address, datasetId]);

  if (loading) return <Loading />;
  if (error)   return <ErrorMsg msg={error} />;
  if (!events?.length) return (
    <div style={{ padding: '16px', fontSize: 11, color: '#94a3b8' }}>No timeline events.</div>
  );

  return (
    <div className="inv-section">
      <div className="inv-section__title">Events ({events.length})</div>
      <div className="inv-timeline">
        {events.map((ev, i) => {
          const isOut = ev.direction === 'outbound';
          return (
            <div key={i} className={`inv-tl-item inv-tl-item--${isOut ? 'out' : 'in'}`}>
              <div className={`inv-tl-dot inv-tl-dot--${isOut ? 'out' : 'in'}`} />
              <div className="inv-tl-body">
                <div className="inv-tl-time">
                  {ev.timestamp ? new Date(ev.timestamp).toLocaleString(undefined, {
                    dateStyle: 'short', timeStyle: 'short'
                  }) : '—'}
                </div>
                <div className="inv-tl-label">
                  {isOut ? 'Sent' : 'Received'} · {ev.txid?.slice(0, 12)}…
                </div>
                {ev.amount_btc != null && (
                  <div className="inv-tl-amount">{ev.amount_btc} BTC</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── P4c: Transaction inspector ────────────────────────────────────────────
function TransactionInspector({ txid, datasetId }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!txid) return;
    setLoading(true);
    getTransactionDetail(txid, datasetId)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.detail ?? e.message ?? 'Failed to load transaction.'); setLoading(false); });
  }, [txid, datasetId]);

  if (loading) return <Loading />;
  if (error)   return <ErrorMsg msg={error} />;
  if (!data || data.error) return <ErrorMsg msg={data?.error ?? 'Transaction not found.'} />;

  const tx        = data.transaction ?? {};
  const inputs    = data.inputs       ?? [];
  const outputs   = data.outputs      ?? [];
  const broadcasts = data.broadcasts  ?? [];
  const dsts      = data.destinations ?? [];

  return (
    <div className="inv-inspector__body">
      <Section title="Transaction">
        <Kv label="TXID"          value={tx.txid}             addr />
        <Kv label="Timestamp"     value={tx.timestamp ? new Date(tx.timestamp).toLocaleString() : null} mono={false} />
        <Kv label="Fee"           value={tx.fee_btc != null ? `${tx.fee_btc} BTC` : null} />
        <Kv label="Fee Ratio"     value={tx.fee_ratio != null ? `${(tx.fee_ratio * 100).toFixed(4)}%` : null} />
        <Kv label="Input Vol"     value={tx.input_volume_btc  != null ? `${tx.input_volume_btc} BTC`  : null} />
        <Kv label="Output Vol"    value={tx.output_volume_btc != null ? `${tx.output_volume_btc} BTC` : null} />
        <Kv label="Script Type"   value={tx.script_type}      mono={false} />
        {tx.balance_delta != null && tx.balance_delta < -0.0001 && (
          <div className="inv-kv">
            <span className="inv-kv__key">Balance</span>
            <span className="inv-kv__val" style={{ color: 'var(--gov-red)' }}>⚠ Violation ({tx.balance_delta} BTC)</span>
          </div>
        )}
      </Section>

      {inputs.length > 0 && (
        <Section title={`Inputs (${inputs.length})`}>
          {inputs.map((inp, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>
                {inp.address?.slice(0, 18)}…
              </span>
              <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: inp.flagged ? 'var(--gov-red)' : '#0f172a' }}>
                {inp.amount_btc} BTC{inp.flagged ? ' ⚠' : ''}
              </span>
            </div>
          ))}
        </Section>
      )}

      {outputs.length > 0 && (
        <Section title={`Outputs (${outputs.length})`}>
          {outputs.map((out, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>
                {out.address?.slice(0, 18)}…
              </span>
              <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: out.flagged ? 'var(--gov-red)' : '#0f172a' }}>
                {out.amount_btc} BTC{out.flagged ? ' ⚠' : ''}
              </span>
            </div>
          ))}
        </Section>
      )}

      {broadcasts.length > 0 && (
        <Section title="Broadcast IPs">
          {broadcasts.slice(0, 5).map((b, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__key" style={{ fontFamily: 'var(--mono)', fontSize: 9 }}>{b.ip}</span>
              <span className="inv-kv__val" style={{ fontSize: 9 }}>
                {b.state} · conf {Math.round((b.confidence ?? 1) * 100)}%
              </span>
            </div>
          ))}
        </Section>
      )}

      {dsts.length > 0 && (
        <Section title="Observed Destination IPs">
          {dsts.slice(0, 3).map((d, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__key" style={{ fontFamily: 'var(--mono)', fontSize: 9 }}>{d.ip}</span>
              <span className="inv-kv__val" style={{ fontSize: 9 }}>{d.state} · :{d.dst_port}</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

// ── P4d: IP inspector ──────────────────────────────────────────────────────
function IpInspector({ ip, datasetId }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!ip) return;
    setLoading(true);
    getIpDetail(ip, datasetId)
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.detail ?? e.message ?? 'Failed to load IP.'); setLoading(false); });
  }, [ip, datasetId]);

  if (loading) return <Loading />;
  if (error)   return <ErrorMsg msg={error} />;
  if (!data)   return <ErrorMsg msg="IP not found." />;

  const geo     = data.geo     ?? {};
  const network = data.network ?? {};
  const obs     = data.observations     ?? [];
  const wallets = data.linked_wallets   ?? [];
  const txids   = data.linked_transactions ?? [];

  return (
    <div className="inv-inspector__body">
      <Section title="Geographic Information">
        <Kv label="IP"       value={data.ip}      addr />
        <Kv label="City"     value={geo.city}     mono={false} />
        <Kv label="State"    value={geo.state}    mono={false} />
        <Kv label="Country"  value={geo.country}  mono={false} />
        {geo.latitude  != null && <Kv label="Lat"  value={geo.latitude.toFixed(4)}  />}
        {geo.longitude != null && <Kv label="Long" value={geo.longitude.toFixed(4)} />}
        {geo.source?.provider && (
          <div className="inv-kv">
            <span className="inv-kv__key">Source</span>
            <span className="inv-kv__val" style={{ fontFamily: 'var(--font)', fontSize: 9, color: '#64748b' }}>
              {geo.source.provider}{geo.source.fallback ? ' (fallback)' : ''}
            </span>
          </div>
        )}
      </Section>

      <Section title="Network">
        <Kv label="ASN" value={network.asn} />
        <Kv label="Organisation" value={network.organization} mono={false} />
      </Section>

      <div style={{
        margin: '8px 16px',
        padding: '8px 10px',
        background: '#f8fafc',
        border: '1px solid #e2e8f0',
        fontSize: 9,
        color: '#64748b',
        lineHeight: 1.5,
      }}>
        ⚠ IP-derived geographic information represents the observed network
        endpoint and does not establish the physical location of the wallet,
        user, or device.
      </div>

      {obs.length > 0 && (
        <Section title={`Broadcast Observations (${obs.length})`}>
          {obs.slice(0, 8).map((o, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>
                {o.txid?.slice(0, 16)}…
              </span>
              <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: '#64748b' }}>
                conf {Math.round((o.confidence ?? 1) * 100)}%
              </span>
            </div>
          ))}
          {obs.length > 8 && <div style={{ fontSize: 9, color: '#94a3b8', paddingTop: 4 }}>+{obs.length - 8} more</div>}
        </Section>
      )}

      {wallets.length > 0 && (
        <Section title={`Linked Wallets (${wallets.length})`}>
          {wallets.slice(0, 6).map((w, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>{w.slice(0, 20)}…</span>
            </div>
          ))}
        </Section>
      )}

      {txids.length > 0 && (
        <Section title={`Linked Transactions (${txids.length})`}>
          {txids.slice(0, 6).map((t, i) => (
            <div key={i} className="inv-kv">
              <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>{t.slice(0, 20)}…</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

// ── P4f: Arc / Path panel ─────────────────────────────────────────────────
function ArcInspector({ link, onNavigate }) {
  const src = link?.source?.id ?? link?.source ?? '—';
  const tgt = link?.target?.id ?? link?.target ?? '—';
  const srcAddr = String(src).replace(/^wallet:/, '');
  const tgtAddr = String(tgt).replace(/^wallet:/, '');
  const isWalletToWallet = String(src).startsWith('wallet:') && String(tgt).startsWith('wallet:');

  return (
    <div className="inv-inspector__body">
      <Section title="Relationship">
        <Kv label="Type" value={link?.type ?? 'RELATED'} />
        <div className="inv-kv">
          <span className="inv-kv__key">From</span>
          <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>{String(src).slice(0, 22)}…</span>
        </div>
        <div className="inv-kv">
          <span className="inv-kv__key">To</span>
          <span className="inv-kv__val inv-kv__val--addr" style={{ fontSize: 9 }}>{String(tgt).slice(0, 22)}…</span>
        </div>
        {link?.amount_btc != null && <Kv label="Amount" value={`${link.amount_btc} BTC`} />}
        {link?.risk?.is_risk_path && (
          <div className="inv-kv">
            <span className="inv-kv__key">Risk Path</span>
            <span className="inv-kv__val" style={{ color: 'var(--gov-red)' }}>⚠ Yes</span>
          </div>
        )}
      </Section>
      {isWalletToWallet && (
        <Section title="Investigate Endpoints">
          <div style={{ display: 'flex', gap: 6, padding: '4px 0' }}>
            <button className="inv-action-btn inv-action-btn--primary" style={{ flex: 1 }}
              onClick={() => onNavigate(srcAddr)}>
              From →
            </button>
            <button className="inv-action-btn" style={{ flex: 1 }}
              onClick={() => onNavigate(tgtAddr)}>
              To →
            </button>
          </div>
        </Section>
      )}
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────
export default function InspectorPanel({
  selectedNode,
  selectedLink,
  onNavigate,
  onClear,
  datasetId = null,
}) {
  // Nothing selected
  if (!selectedNode && !selectedLink) {
    return (
      <div className="inv-inspector__empty">
        <span className="inv-inspector__empty-icon">🔍</span>
        <span className="inv-inspector__empty-text">
          Click a wallet, transaction, IP,<br />or arc to investigate
        </span>
      </div>
    );
  }

  // Arc selected (P4f)
  if (selectedLink && !selectedNode) {
    return (
      <>
        <div className="inv-inspector__header">
          <div className="inv-inspector__type">Arc / Relationship</div>
          <div className="inv-inspector__title">{selectedLink.type ?? 'RELATED'}</div>
        </div>
        <ArcInspector link={selectedLink} onNavigate={onNavigate} />
        <div className="inv-inspector__actions">
          <button className="inv-action-btn inv-btn--reset" onClick={onClear}>Clear</button>
        </div>
      </>
    );
  }

  // Node selected
  const nodeType = selectedNode?.type;

  // Wallet (P4b)
  if (nodeType === 'wallet') {
    const addr = selectedNode.address ?? selectedNode.id?.replace(/^wallet:/, '');
    return (
      <>
        <div className="inv-inspector__header">
          <div className="inv-inspector__type">Wallet</div>
          <div className="inv-inspector__title">{addr}</div>
          {selectedNode.risk_score != null && (
            <div style={{ marginTop: 4 }}>
              <RiskBadge score={Math.round(selectedNode.risk_score)} />
            </div>
          )}
        </div>
        <WalletInspector address={addr} onNavigate={onNavigate} datasetId={datasetId} />
        <div className="inv-inspector__actions">
          <button className="inv-action-btn inv-btn--reset" onClick={onClear}>Clear</button>
        </div>
      </>
    );
  }

  // Transaction (P4c)
  if (nodeType === 'transaction') {
    const txid = selectedNode.label ?? selectedNode.id?.replace(/^tx:/, '');
    return (
      <>
        <div className="inv-inspector__header">
          <div className="inv-inspector__type">Transaction</div>
          <div className="inv-inspector__title" style={{ fontSize: 11 }}>{txid}</div>
        </div>
        <TransactionInspector txid={txid} datasetId={datasetId} />
        <div className="inv-inspector__actions">
          <button className="inv-action-btn inv-btn--reset" onClick={onClear}>Clear</button>
        </div>
      </>
    );
  }

  // IP (P4d)
  if (nodeType === 'ip') {
    const ip = selectedNode.ip ?? selectedNode.id?.replace(/^ip:/, '');
    return (
      <>
        <div className="inv-inspector__header">
          <div className="inv-inspector__type">Observed IP</div>
          <div className="inv-inspector__title">{ip}</div>
          {selectedNode.state && (
            <div className="inv-inspector__subtitle">{selectedNode.state} · {selectedNode.asn ?? ''}</div>
          )}
        </div>
        <IpInspector ip={ip} datasetId={datasetId} />
        <div className="inv-inspector__actions">
          <button className="inv-action-btn inv-btn--reset" onClick={onClear}>Clear</button>
        </div>
      </>
    );
  }

  // Unknown entity type
  return (
    <>
      <div className="inv-inspector__header">
        <div className="inv-inspector__type">{nodeType ?? 'Entity'}</div>
        <div className="inv-inspector__title">{selectedNode.id}</div>
      </div>
      <div className="inv-inspector__body">
        <div className="inv-section">
          <div style={{ fontSize: 11, color: '#64748b' }}>
            No detailed investigation available for this entity type.
          </div>
        </div>
      </div>
      <div className="inv-inspector__actions">
        <button className="inv-action-btn inv-btn--reset" onClick={onClear}>Clear</button>
      </div>
    </>
  );
}
