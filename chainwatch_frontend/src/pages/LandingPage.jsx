/**
 * LandingPage.jsx — /
 *
 * Root landing page. Uses shared CwNav and existing ChainWatch visual language:
 * gov-blue, saffron, white typography, flat cards, monospace values.
 *
 * No fake data. No invented metrics. CTAs link to real working routes.
 */
import { useNavigate } from 'react-router-dom';
import CwNav from '../components/CwNav';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#f2f4f7' }}>
      <CwNav status="ok" />

      {/* ── Hero ── */}
      <section style={{
        background: 'var(--gov-blue)',
        borderBottom: '4px solid var(--gov-saffron)',
        padding: '72px 32px 64px',
        color: '#fff',
      }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', gap: 48, alignItems: 'center', flexWrap: 'wrap' }}>
          <img
            src="/emblem_india.svg"
            alt="Emblem of India"
            style={{ height: 80, filter: 'brightness(0) invert(1)', opacity: 0.9, flexShrink: 0 }}
          />
          <div style={{ flex: 1, minWidth: 280 }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>
              National Technical Research Organisation · Cyber Intelligence Division
            </div>
            <h1 style={{ fontSize: 42, fontWeight: 800, lineHeight: 1.1, marginBottom: 14, letterSpacing: '-0.02em' }}>
              ChainWatch
            </h1>
            <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.78)', maxWidth: 580, lineHeight: 1.65, marginBottom: 32 }}>
              Offline blockchain forensic intelligence — correlate IP broadcast data with
              on-chain transactions, detect laundering typologies, and trace risk across
              the transaction graph. No external APIs. No cloud dependencies.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button
                onClick={() => navigate('/dashboard')}
                style={{
                  background: 'var(--gov-saffron)', color: '#0f172a',
                  border: 'none', padding: '12px 28px',
                  fontWeight: 800, fontSize: 13, cursor: 'pointer',
                  borderRadius: 2, fontFamily: 'inherit',
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                }}
              >
                Enter Dashboard →
              </button>
              <button
                onClick={() => navigate('/about')}
                style={{
                  background: 'rgba(255,255,255,0.10)', color: '#fff',
                  border: '1px solid rgba(255,255,255,0.28)', padding: '12px 28px',
                  fontWeight: 700, fontSize: 13, cursor: 'pointer',
                  borderRadius: 2, fontFamily: 'inherit',
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                }}
              >
                About ChainWatch
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ── What it is ── */}
      <section style={{ background: '#ffffff', padding: '60px 32px', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--gov-saffron)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>
            Platform Overview
          </div>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: '#0f172a', marginBottom: 14, letterSpacing: '-0.01em' }}>
            Bitcoin transaction intelligence, fully offline
          </h2>
          <p style={{ fontSize: 15, color: '#475569', maxWidth: 680, lineHeight: 1.75, marginBottom: 40 }}>
            ChainWatch ingests raw Bitcoin network captures and blockchain metadata, correlates
            broadcast IP addresses with transaction records using exponential-decay timing analysis,
            and runs a multi-stage forensic pipeline — all on-premise, with no outbound network calls.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
            {[
              {
                icon: '🌐',
                color: 'var(--gov-blue)',
                title: 'IP-to-TX Correlation',
                body: 'Bind the P2P broadcast IP directly to the UTXO transaction. Resolve offline against MaxMind GeoLite2 to map transactions to ISP, city, and ASN.',
              },
              {
                icon: '🔗',
                color: 'var(--gov-saffron)',
                title: 'Laundering Detection',
                body: 'Peeling chains, CoinJoin mixing, and co-spending heuristics detected via graph traversal — not hardcoded rules.',
              },
              {
                icon: '🤖',
                color: 'var(--gov-green)',
                title: 'AI Anomaly Detection',
                body: 'IsolationForest across 14 behavioural features. SHAP TreeExplainer provides per-wallet feature attribution — not just a score.',
              },
              {
                icon: '✦',
                color: '#eab308',
                title: 'Neural Investigation Map',
                body: 'Interactive force-directed graph. Progressive hop expansion, branch isolation, selected-path gold highlighting, unified entity inspector.',
              },
            ].map((card, i) => (
              <div
                key={i}
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderTop: `3px solid ${card.color}`,
                  padding: '20px 22px',
                  borderRadius: 2,
                }}
              >
                <div style={{ fontSize: 22, marginBottom: 10 }}>{card.icon}</div>
                <div style={{ fontSize: 12, fontWeight: 800, color: '#0f172a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {card.title}
                </div>
                <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.65 }}>
                  {card.body}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section style={{ background: '#f8fafc', padding: '60px 32px', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--gov-saffron)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>
            Investigation Workflow
          </div>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: '#0f172a', marginBottom: 36, letterSpacing: '-0.01em' }}>
            From raw ledger to ranked forensic leads
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 640 }}>
            {[
              { n: '01', label: 'Ingest', desc: 'Upload a CSV ledger containing network captures (src/dst IP, ports, timing) alongside blockchain metadata (TXIDs, wallet addresses, amounts, script type, fee). The backend validates, enriches with GeoIP, and correlates broadcasts.' },
              { n: '02', label: 'Detect & Score', desc: 'IsolationForest flags statistically anomalous wallets. Peeling chain and CoinJoin detectors identify laundering typologies. Risk propagates across the transaction graph with 0.70× per-hop decay. SHAP explains each flag.' },
              { n: '03', label: 'Investigate', desc: 'Open any flagged wallet in the Neural Map. Expand 1–N hops, isolate branches, click arcs to select paths, and inspect wallet/transaction/IP detail panels — all backed by live Neo4j queries.' },
            ].map((step, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  gap: 20,
                  padding: '20px 0',
                  borderBottom: i < 2 ? '1px solid #e2e8f0' : 'none',
                }}
              >
                <div style={{
                  flexShrink: 0,
                  width: 36, height: 36,
                  borderRadius: 2,
                  background: 'var(--gov-blue)', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 800, fontFamily: 'var(--mono)',
                }}>
                  {step.n}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#0f172a', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {step.label}
                  </div>
                  <div style={{ fontSize: 13, color: '#64748b', lineHeight: 1.7 }}>
                    {step.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Product preview CTAs ── */}
      <section style={{ background: '#ffffff', padding: '60px 32px', borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--gov-saffron)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>
            Get Started
          </div>
          <h2 style={{ fontSize: 28, fontWeight: 800, color: '#0f172a', marginBottom: 32, letterSpacing: '-0.01em' }}>
            Choose your entry point
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {[
              { label: 'Dashboard', href: '/dashboard', desc: 'Overview metrics, threat ticker, geospatial map, alert watchlist.', icon: '📊', primary: false },
              { label: 'Neural Map', href: '/investigate', desc: 'Open the investigation workstation. Select a wallet to begin.', icon: '✦', primary: true },
              { label: 'Alerts', href: '/alerts', desc: 'Browse ranked alerts with server-side filter and sort.', icon: '🚨', primary: false },
              { label: 'Ingest', href: '/ingest', desc: 'Upload a CSV ledger and run the full forensic pipeline.', icon: '⬆', primary: false },
            ].map((item, i) => (
              <button
                key={i}
                onClick={() => navigate(item.href)}
                style={{
                  background: item.primary ? 'var(--gov-blue)' : '#f8fafc',
                  border: item.primary ? '2px solid var(--gov-blue)' : '1px solid #cbd5e1',
                  color: item.primary ? '#ffffff' : '#0f172a',
                  padding: '20px 20px',
                  borderRadius: 2,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: 'inherit',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  if (!item.primary) { e.currentTarget.style.borderColor = 'var(--gov-blue)'; e.currentTarget.style.background = 'var(--gov-blue-dim)'; }
                }}
                onMouseLeave={e => {
                  if (!item.primary) { e.currentTarget.style.borderColor = '#cbd5e1'; e.currentTarget.style.background = '#f8fafc'; }
                }}
              >
                <div style={{ fontSize: 24, marginBottom: 10 }}>{item.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {item.label}
                </div>
                <div style={{ fontSize: 12, color: item.primary ? 'rgba(255,255,255,0.75)' : '#64748b', lineHeight: 1.55 }}>
                  {item.desc}
                </div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Offline / local intelligence ── */}
      <section style={{ background: 'var(--gov-blue)', padding: '56px 32px' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', gap: 48, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>
              Deployment
            </div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#fff', marginBottom: 14, letterSpacing: '-0.01em' }}>
              Fully offline · air-gap capable
            </h2>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.7)', lineHeight: 1.75 }}>
              All GeoIP resolution uses local MaxMind MMDB files. All ML inference runs
              on-process in Python. Neo4j runs in a local Docker container.
              No external API calls are made at runtime.
            </p>
          </div>
          <div style={{ flex: 1, minWidth: 260, fontFamily: 'var(--mono)', fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 2.2 }}>
            {[
              ['Frontend',  'React 19 · Vite 8'],
              ['Backend',   'FastAPI 0.115 · Python 3.14'],
              ['ML',        'scikit-learn 1.5 · SHAP 0.46 · NetworkX 3.4'],
              ['Database',  'Neo4j 5.12 (Docker)'],
              ['GeoIP',     'MaxMind GeoLite2 City + ASN'],
              ['Reports',   'WeasyPrint 63'],
            ].map(([k, v]) => (
              <div key={k}>
                <span style={{ color: 'var(--gov-saffron)', fontWeight: 700 }}>{k}</span>
                <span style={{ color: 'rgba(255,255,255,0.4)', margin: '0 8px' }}>·</span>
                <span>{v}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="footer-main">
        <div className="footer-columns">
          <div className="footer-col">
            <h3>About ChainWatch</h3>
            <p>An advanced offline intelligence system designed by NTRO to monitor, detect, and analyze illicit cryptocurrency transaction traffic across Indian jurisdictions.</p>
          </div>
          <div className="footer-col">
            <h3>Quick Links</h3>
            <ul>
              <li><a href="/dashboard">Dashboard</a></li>
              <li><a href="/investigate">Neural Map</a></li>
              <li><a href="/alerts">Alerts</a></li>
              <li><a href="/search">Search</a></li>
              <li><a href="/ingest">Ingest Ledger</a></li>
              <li><a href="/about">About &amp; Methodology</a></li>
            </ul>
          </div>
          <div className="footer-col">
            <h3>Nodal Agency</h3>
            <p><strong>NTRO</strong><br />National Technical Research Organisation<br />Government of India<br />Cyber Intelligence Division</p>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 National Technical Research Organisation, Government of India. All rights reserved.</p>
          <div className="footer-bottom-links">
            <a href="/about">About</a><span>|</span>
            <a href="/about#methodology">Methodology</a><span>|</span>
            <a href="/about#architecture">Architecture</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
