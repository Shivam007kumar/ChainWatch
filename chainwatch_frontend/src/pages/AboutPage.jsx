/**
 * AboutPage.jsx — /about
 * ───────────────────────
 * Landing page / methodology document for ChainWatch.
 * Follows the original 13-section storytelling structure.
 *
 * Rules applied:
 *   - No fake intelligence, no fake login, no fake Tor/IPsum claims
 *   - Data sources listed only what the backend actually uses
 *   - CTA links to real working pages (/ingest, /alerts, /investigate)
 *   - No external CDN images — uses local /blockchain.png and /emblem_india.svg
 */
import { useNavigate } from 'react-router-dom';
import CwNav from '../components/CwNav';

// ── Section wrapper ────────────────────────────────────────────────────────
function Section({ id, bg = '#ffffff', children }) {
  return (
    <section id={id} style={{
      background: bg,
      padding: '72px 32px',
      borderBottom: '1px solid #e2e8f0',
    }}>
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        {children}
      </div>
    </section>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 800, color: 'var(--gov-saffron)',
      textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 12,
    }}>
      {children}
    </div>
  );
}

function H2({ children }) {
  return (
    <h2 style={{
      fontSize: 30, fontWeight: 800, color: '#0f172a',
      marginBottom: 16, lineHeight: 1.2, letterSpacing: '-0.02em',
    }}>
      {children}
    </h2>
  );
}

function Body({ children }) {
  return (
    <p style={{
      fontSize: 15, color: '#475569', lineHeight: 1.75, marginBottom: 16, maxWidth: 680,
    }}>
      {children}
    </p>
  );
}

function FeatureGrid({ items }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
      gap: 20, marginTop: 32,
    }}>
      {items.map((item, i) => (
        <div key={i} style={{
          background: '#f8fafc', border: '1px solid #e2e8f0',
          borderTop: `3px solid ${item.color ?? 'var(--gov-blue)'}`,
          padding: '20px 22px', borderRadius: 2,
        }}>
          <div style={{ fontSize: 22, marginBottom: 10 }}>{item.icon}</div>
          <div style={{ fontSize: 13, fontWeight: 800, color: '#0f172a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {item.title}
          </div>
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
            {item.body}
          </div>
        </div>
      ))}
    </div>
  );
}

function FlowStep({ n, label, desc }) {
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 20 }}>
      <div style={{
        flexShrink: 0, width: 32, height: 32, borderRadius: '50%',
        background: 'var(--gov-blue)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 800,
      }}>
        {n}
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 800, color: '#0f172a', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {label}
        </div>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>{desc}</div>
      </div>
    </div>
  );
}

function SourceBadge({ label, detail }) {
  return (
    <div style={{
      display: 'inline-flex', flexDirection: 'column', gap: 3,
      background: '#f1f5f9', border: '1px solid #cbd5e1',
      padding: '10px 14px', borderRadius: 2, minWidth: 140,
    }}>
      <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--gov-blue)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 11, color: '#64748b' }}>{detail}</div>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function AboutPage() {
  const navigate = useNavigate();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#f8fafc' }}>
      <CwNav status="ok" />

      {/* 01 — Hero */}
      <section style={{
        background: 'var(--gov-blue)',
        borderBottom: '4px solid var(--gov-saffron)',
        padding: '80px 32px 72px',
        color: '#fff',
      }}>
        <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', gap: 48, alignItems: 'center', flexWrap: 'wrap' }}>
          <img src="/emblem_india.svg" alt="Emblem of India"
               style={{ height: 80, filter: 'brightness(0) invert(1)', opacity: 0.9, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: 'rgba(255,255,255,0.6)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 12 }}>
              National Technical Research Organisation · Cyber Intelligence Division
            </div>
            <h1 style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.1, marginBottom: 16, letterSpacing: '-0.02em' }}>
              ChainWatch
            </h1>
            <p style={{ fontSize: 17, color: 'rgba(255,255,255,0.8)', maxWidth: 600, lineHeight: 1.65, marginBottom: 28 }}>
              An offline blockchain forensic intelligence platform for detecting, mapping,
              and investigating illicit cryptocurrency transaction patterns across Indian jurisdictions.
            </p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button
                onClick={() => navigate('/ingest')}
                style={{
                  background: 'var(--gov-saffron)', color: '#0f172a',
                  border: 'none', padding: '11px 22px', fontWeight: 800,
                  fontSize: 13, cursor: 'pointer', borderRadius: 2, fontFamily: 'inherit',
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                }}
              >
                Ingest Ledger →
              </button>
              <button
                onClick={() => navigate('/alerts')}
                style={{
                  background: 'rgba(255,255,255,0.12)', color: '#fff',
                  border: '1px solid rgba(255,255,255,0.3)', padding: '11px 22px',
                  fontWeight: 700, fontSize: 13, cursor: 'pointer', borderRadius: 2,
                  fontFamily: 'inherit', letterSpacing: '0.04em', textTransform: 'uppercase',
                }}
              >
                View Alerts
              </button>
              <button
                onClick={() => navigate('/')}
                style={{
                  background: 'transparent', color: 'rgba(255,255,255,0.65)',
                  border: '1px solid transparent', padding: '11px 22px',
                  fontWeight: 700, fontSize: 13, cursor: 'pointer', borderRadius: 2,
                  fontFamily: 'inherit', letterSpacing: '0.04em', textTransform: 'uppercase',
                }}
              >
                Dashboard
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 02 — The Problem */}
      <Section id="problem" bg="#ffffff">
        <SectionLabel>02 / The Problem</SectionLabel>
        <H2>Blockchain transparency creates a paradox</H2>
        <Body>
          Bitcoin's public ledger makes every transaction visible — yet pseudonymous wallet addresses,
          complex multi-hop laundering sequences, and the volume of on-chain activity make manual
          investigation impractical. Standard blockchain explorers show what happened. They cannot
          tell investigators <em>where the transaction originated</em>, which wallets belong to the same
          actor, or how risk propagates across a transaction network.
        </Body>
        <Body>
          Field investigators need to correlate network-layer data (IP addresses, broadcast timing,
          ASN routing) with blockchain-layer data (transaction IDs, wallet addresses, amounts) — and
          do it offline, without depending on external APIs or cloud services.
        </Body>
        <FeatureGrid items={[
          { icon: '🔍', color: 'var(--gov-red)',    title: 'Pseudonymity',    body: 'Wallet addresses reveal nothing about real-world identity. Standard explorers stop here.' },
          { icon: '🌐', color: 'var(--gov-blue)',   title: 'Network Layer Gap', body: 'The P2P broadcast IP that propagated a transaction is not recorded on-chain.' },
          { icon: '🔗', color: 'var(--gov-saffron)', title: 'Graph Complexity',  body: 'Peeling chains, CoinJoin mixers, and multi-hop hops are invisible to linear analysis.' },
          { icon: '📊', color: '#475569',           title: 'Scale',            body: 'Thousands of transactions per dataset — impossible to manually trace risk propagation.' },
        ]} />
      </Section>

      {/* 03 — How ChainWatch Works */}
      <Section id="how-it-works" bg="#f8fafc">
        <SectionLabel>03 / How ChainWatch Works</SectionLabel>
        <H2>End-to-end forensic pipeline</H2>
        <Body>
          ChainWatch ingests raw Bitcoin network + transaction metadata and runs it through a
          seven-stage pipeline — entirely offline, on-premise, without any external API calls.
        </Body>
        <div style={{ marginTop: 32, maxWidth: 640 }}>
          <FlowStep n={1} label="Ingest"
            desc="Upload a CSV ledger containing network captures (src/dst IP, ports, timing) and blockchain metadata (TXID, wallet addresses, amounts, script type, fee)." />
          <FlowStep n={2} label="Enrich"
            desc="Each IP address is resolved against local MaxMind GeoLite2 databases (city + ASN) and a CSV fallback — zero outbound calls. State, city, ASN, and lat/lng are attached to every record." />
          <FlowStep n={3} label="Correlate"
            desc="Broadcast IP confidence is computed using exponential decay: confidence = exp(−Δt / τ). Only captures within 30 seconds of the earliest broadcast for a transaction are considered genuine." />
          <FlowStep n={4} label="Detect"
            desc="IsolationForest (200 estimators) flags anomalous wallets across 14 behavioural features. KMeans (6 clusters) groups wallets by behavioural signature. Peeling chain (80/20 split heuristic, NetworkX path traversal) and CoinJoin (≥3 inputs, uniform outputs) detectors flag specific laundering typologies." />
          <FlowStep n={5} label="Explain"
            desc="SHAP TreeExplainer computes exact Shapley values for each flagged wallet — showing which of the 14 features drove the anomaly score, by how many standard deviations, and in which direction." />
          <FlowStep n={6} label="Propagate"
            desc="Risk scores decay across transaction hops using BFS: R(w) = R(seed) × 0.70^d. Co-spending wallets (CIOU heuristic) receive an additional 0.85× boost. Every wallet in the graph receives a propagated risk level." />
          <FlowStep n={7} label="Persist"
            desc="Neo4j graph database stores Wallet, Transaction, and IP nodes with typed relationships (SENT, RECEIVED_BY, BROADCAST, OBSERVED_DESTINATION, SAME_ENTITY_AS). All alerts, evidence, and SHAP attributions are persisted with stable IDs." />
        </div>
      </Section>

      {/* 04 — Neural Transaction Mapping */}
      <Section id="neural-map" bg="#ffffff">
        <SectionLabel>04 / Neural Transaction Mapping</SectionLabel>
        <H2>Investigation-first graph exploration</H2>
        <Body>
          The Neural Map is the primary investigation surface — not a static visualisation.
          Investigators control exactly what they see and how far they traverse the transaction graph.
        </Body>
        <FeatureGrid items={[
          { icon: '🎯', color: 'var(--gov-blue)',    title: 'Progressive Disclosure', body: '1 → 2 → 3 → N hops from any wallet. The graph expands on demand, not all at once.' },
          { icon: '🔀', color: 'var(--gov-saffron)', title: 'Direction Control',       body: 'Trace forward (follow money), backward (trace origin), or both directions simultaneously.' },
          { icon: '✦',  color: '#eab308',            title: 'Selected Path Gold',      body: 'Clicking a wallet or arc highlights the path in gold. Directional animation runs only on the selected path.' },
          { icon: '🌿', color: 'var(--gov-green)',   title: 'Branch Management',       body: 'Expand, collapse, isolate a sub-branch, or hide unrelated nodes — without losing graph state.' },
        ]} />
      </Section>

      {/* 05 — Investigation Workflow */}
      <Section id="workflow" bg="#f8fafc">
        <SectionLabel>05 / Investigation Workflow</SectionLabel>
        <H2>From alert to evidence in six steps</H2>
        <div style={{ marginTop: 32, maxWidth: 640 }}>
          <FlowStep n={1} label="Dashboard → Alert"
            desc="The executive dashboard surfaces the highest-risk alerts sorted by propagated risk score. Each alert links directly to an investigation." />
          <FlowStep n={2} label="Open Investigation"
            desc="Navigate to /investigate/:address. The wallet's neighbourhood graph loads at 2 hops. Flagged wallets appear immediately in red." />
          <FlowStep n={3} label="Expand Graph"
            desc="Increase hops (1 → 2 → 3 → N) to trace the money flow forward or backward. Branch-isolate suspicious sub-trees." />
          <FlowStep n={4} label="Select Entity"
            desc="Click any wallet, transaction, or IP. The right-side inspector fetches full detail: risk score, SHAP attribution, broadcast IPs, timeline." />
          <FlowStep n={5} label="Trace Path"
            desc="Click any arc to select it. The path highlights gold, metrics strip shows hop count and total BTC. Investigate either endpoint." />
          <FlowStep n={6} label="Export Evidence"
            desc="Generate a PDF dossier per wallet — includes risk assessment, XAI feature attribution table, linked transaction IDs, and IP intelligence." />
        </div>
      </Section>

      {/* 06 — Network Intelligence */}
      <Section id="network-intel" bg="#ffffff">
        <SectionLabel>06 / Network Intelligence</SectionLabel>
        <H2>IP-layer correlation with blockchain data</H2>
        <Body>
          ChainWatch correlates the network-layer broadcast IP with the on-chain transaction record.
          This produces an IP → Transaction → Wallet chain that is not available from blockchain
          explorers alone.
        </Body>
        <Body>
          <strong>Important distinction:</strong> IP-derived geographic information represents the
          observed network endpoint at broadcast time. It does not establish the physical location
          of the wallet owner, user, or device.
        </Body>
        <div style={{ marginTop: 28, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <SourceBadge label="MaxMind GeoLite2 City" detail="State · City · Lat/Lng" />
          <SourceBadge label="MaxMind GeoLite2 ASN"  detail="ASN number · Organisation" />
          <SourceBadge label="IP_Address.csv"         detail="Indian ISP range fallback" />
          <SourceBadge label="Broadcast Confidence"   detail="exp(−Δt / τ) decay scoring" />
        </div>
      </Section>

      {/* 07 — Threat Intelligence */}
      <Section id="threat-intel" bg="#f8fafc">
        <SectionLabel>07 / Threat Intelligence Providers</SectionLabel>
        <H2>Detection evidence and data sources</H2>
        <Body>
          ChainWatch uses only data sources that are fully available offline. Each detection
          produces structured evidence with the source clearly labelled.
        </Body>
        <FeatureGrid items={[
          { icon: '🌍', color: 'var(--gov-blue)',    title: 'MaxMind GeoLite2',   body: 'City and ASN databases. Offline MMDB files. No account or API key required at runtime.' },
          { icon: '📋', color: 'var(--gov-saffron)', title: 'Indian IP Registry', body: 'CSV range table of Indian ISP address blocks with state and city attribution. CSV fallback when MaxMind is unavailable.' },
          { icon: '🔬', color: 'var(--gov-green)',   title: 'IsolationForest',    body: 'sklearn 1.5.2 · 14 behavioural features · 200 estimators · contamination=0.10. Flags statistically anomalous wallets.' },
          { icon: '✨', color: '#8b5cf6',            title: 'SHAP v0.46',         body: 'TreeExplainer on the fitted IsolationForest. Exact Shapley values — not approximations. Top-3 features per alert.' },
          { icon: '🔗', color: '#0d9488',            title: 'NetworkX 3.4',       body: 'Directed graph traversal for peeling chain detection. Path search bounded by cutoff to prevent graph explosion.' },
          { icon: '🏷️', color: '#475569',            title: 'Neo4j 5.12',         body: 'Local Docker container. Wallet, Transaction, IP, Dataset, Alert nodes. MERGE-idempotent writes.' },
        ]} />
        <div style={{
          marginTop: 28, padding: '14px 16px', background: '#fffbeb',
          border: '1px solid var(--gov-saffron)', borderLeft: '3px solid var(--gov-saffron)',
          fontSize: 12, color: '#78350f', lineHeight: 1.6, maxWidth: 640,
        }}>
          ⚠ IPsum threat reputation scoring and Tor exit node detection are referenced in the
          original system specification but are not active in the current deployment. These
          data sources are reserved for a future release.
        </div>
      </Section>

      {/* 08 — XAI / Risk Explanations */}
      <Section id="xai" bg="#ffffff">
        <SectionLabel>08 / Explainable AI</SectionLabel>
        <H2>Why was this wallet flagged?</H2>
        <Body>
          Every alert produced by ChainWatch is backed by a SHAP feature attribution table.
          Investigators can see exactly which behavioural signal drove the anomaly score —
          not just a percentage, but a directional, sigma-normalised explanation.
        </Body>
        <div style={{ marginTop: 28, background: '#f8fafc', border: '1px solid #e2e8f0', padding: '20px 24px', maxWidth: 560 }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Example SHAP Attribution
          </div>
          {[
            { label: 'Transaction velocity (tx/hr)', pct: '+41%', dir: 'pos', sigma: '2.4σ above mean' },
            { label: 'Distinct ISP/ASN providers',  pct: '+29%', dir: 'pos', sigma: '1.9σ above mean' },
            { label: 'Output amount variance',       pct: '+19%', dir: 'pos', sigma: '1.6σ above mean' },
          ].map((row, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', gap: 16,
              padding: '6px 0', borderBottom: i < 2 ? '1px dashed #e2e8f0' : 'none',
              fontSize: 11,
            }}>
              <span style={{ color: '#475569' }}>{row.label}</span>
              <span style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 800, color: '#ef4444' }}>{row.pct}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#94a3b8' }}>{row.sigma}</span>
              </span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14, fontSize: 11, color: '#94a3b8', maxWidth: 560 }}>
          The values above are illustrative. All actual attributions are computed by SHAP TreeExplainer
          on the fitted IsolationForest model for each specific dataset.
        </div>
      </Section>

      {/* 09 — System Architecture */}
      <Section id="architecture" bg="#f8fafc">
        <SectionLabel>09 / System Architecture</SectionLabel>
        <H2>Fully offline · air-gap capable</H2>
        <Body>
          ChainWatch runs entirely on a local machine with no outbound internet connections required
          after initial setup. The backend is a FastAPI service; the graph database is a Docker
          Neo4j container; all ML inference runs on-process in Python.
        </Body>
        <div style={{ marginTop: 24, fontFamily: 'var(--mono)', fontSize: 12, color: '#475569', background: '#ffffff', border: '1px solid #e2e8f0', padding: '20px 24px', lineHeight: 2.2, maxWidth: 540 }}>
          <div style={{ color: '#64748b', fontSize: 10, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: 'var(--font)' }}>Stack</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>Frontend</span> · React 19 · Vite 8 · react-force-graph-2d</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>Backend</span> · FastAPI 0.115 · Python 3.14 · uvicorn</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>ML</span> · scikit-learn 1.5.2 · SHAP 0.46 · NetworkX 3.4</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>Database</span> · Neo4j 5.12 (Docker) · neo4j driver 5.25</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>GeoIP</span> · MaxMind GeoLite2 City + ASN (local .mmdb)</div>
          <div><span style={{ color: 'var(--gov-blue)', fontWeight: 700 }}>Reports</span> · WeasyPrint 63 (PDF generation)</div>
        </div>
      </Section>

      {/* 10 — Methodology & Data Sources */}
      <Section id="methodology" bg="#ffffff">
        <SectionLabel>10 / Methodology</SectionLabel>
        <H2>Detection methodology</H2>
        <Body>
          ChainWatch does not rely on hardcoded rules. The core detection pipeline uses
          unsupervised machine learning across 14 engineered features derived from both
          the network layer and the blockchain layer.
        </Body>
        <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 720 }}>
          {[
            { title: 'Anomaly Detection',   desc: 'IsolationForest with contamination=0.10. Wallets with anomaly scores below the threshold are flagged for investigation.' },
            { title: 'Entity Clustering',   desc: 'KMeans (6 clusters) groups wallets by behavioural signature. Cluster labels are derived from centroid z-scores, not hardcoded strings.' },
            { title: 'Peeling Chains',      desc: 'NetworkX directed graph traversal finds chains of ≥3 consecutive 80/20 output-split transactions. Risk score: 70 + (hops × 5), capped at 95.' },
            { title: 'CoinJoin Detection',  desc: '≥3 distinct input wallets, ≥3 distinct output wallets, output amount variance <2%. Fixed risk score: 85.' },
            { title: 'Risk Propagation',    desc: 'BFS decay from seed wallets: R(w) = R(seed) × 0.70^d. CIOU co-spending boost: 0.85×. Maximum propagation depth: 4 hops.' },
            { title: 'SHAP Attribution',    desc: 'TreeExplainer (exact, not kernel). Sign negation applied because IsolationForest decision_function is negative-anomalous. Top-3 features per alert.' },
          ].map((item, i) => (
            <div key={i} style={{
              padding: '16px 18px', background: '#f8fafc',
              border: '1px solid #e2e8f0', borderRadius: 2,
            }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: '#0f172a', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {item.title}
              </div>
              <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.65 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* 11 — CTA */}
      <Section id="cta" bg="var(--gov-blue)">
        <div style={{ textAlign: 'center', color: '#fff' }}>
          <SectionLabel>Ready to investigate</SectionLabel>
          <h2 style={{ fontSize: 32, fontWeight: 800, marginBottom: 16, lineHeight: 1.2 }}>
            Start a forensic investigation
          </h2>
          <p style={{ fontSize: 15, color: 'rgba(255,255,255,0.75)', marginBottom: 36, maxWidth: 480, margin: '0 auto 36px' }}>
            Upload a dataset, run the pipeline, and trace the money.
          </p>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={() => navigate('/ingest')} style={{
              background: 'var(--gov-saffron)', color: '#0f172a', border: 'none',
              padding: '12px 28px', fontWeight: 800, fontSize: 13, cursor: 'pointer',
              borderRadius: 2, fontFamily: 'inherit', letterSpacing: '0.04em', textTransform: 'uppercase',
            }}>
              Ingest Ledger →
            </button>
            <button onClick={() => navigate('/alerts')} style={{
              background: 'rgba(255,255,255,0.1)', color: '#fff',
              border: '1px solid rgba(255,255,255,0.3)', padding: '12px 28px',
              fontWeight: 700, fontSize: 13, cursor: 'pointer',
              borderRadius: 2, fontFamily: 'inherit', letterSpacing: '0.04em', textTransform: 'uppercase',
            }}>
              View Alerts
            </button>
          </div>
        </div>
      </Section>

      {/* 12 — Footer */}
      <footer style={{
        background: '#0f172a', color: '#cbd5e1',
        padding: '56px 32px 32px',
        borderTop: '4px solid var(--gov-saffron)',
      }}>
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 48,
            paddingBottom: 48,
            borderBottom: '1px solid #1e293b',
            marginBottom: 32,
          }}>
            {/* Brand */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <img src="/emblem_india.svg" alt="Emblem" style={{ height: 36, filter: 'brightness(0) invert(0.7)' }} />
                <div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: '#fff', textTransform: 'uppercase' }}>ChainWatch</div>
                  <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em' }}>NTRO · Cyber Intelligence</div>
                </div>
              </div>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.7 }}>
                Synthetic Bitcoin transaction intelligence platform for offline forensic investigation.
              </p>
            </div>

            {/* Product */}
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                Product
              </div>
              {[
                { label: 'Dashboard',     href: '/' },
                { label: 'Neural Map',    href: '/investigate' },
                { label: 'Alerts',        href: '/alerts' },
                { label: 'Search',        href: '/search' },
                { label: 'Ingest',        href: '/ingest' },
                { label: 'Methodology',   href: '/about#methodology' },
              ].map(({ label, href }) => (
                <div key={label} style={{ marginBottom: 10 }}>
                  <a
                    href={href}
                    onClick={e => { e.preventDefault(); navigate(href.split('#')[0]); }}
                    style={{ color: '#94a3b8', fontSize: 13, textDecoration: 'none', cursor: 'pointer' }}
                    onMouseEnter={e => e.target.style.color = 'var(--gov-saffron)'}
                    onMouseLeave={e => e.target.style.color = '#94a3b8'}
                  >
                    {label}
                  </a>
                </div>
              ))}
            </div>

            {/* Data Sources */}
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                Data Sources
              </div>
              {[
                'MaxMind GeoLite2 City',
                'MaxMind GeoLite2 ASN',
                'Indian IP Address Registry',
                'Neo4j Graph Database',
                'scikit-learn IsolationForest',
                'SHAP TreeExplainer',
                'NetworkX Graph Traversal',
              ].map(s => (
                <div key={s} style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>{s}</div>
              ))}
            </div>

            {/* Nodal Agency */}
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                Nodal Agency
              </div>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.8 }}>
                <strong style={{ color: '#cbd5e1' }}>NTRO</strong><br />
                National Technical Research Organisation<br />
                Government of India<br />
                Cyber Intelligence Division
              </p>
            </div>
          </div>

          {/* Bottom bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ fontSize: 12, color: '#475569' }}>
              © 2026 National Technical Research Organisation, Government of India. All rights reserved.
            </div>
            <div style={{ display: 'flex', gap: 20 }}>
              {[
                { label: 'About',       href: '/about' },
                { label: 'Methodology', href: '/about#methodology' },
                { label: 'Architecture', href: '/about#architecture' },
              ].map(({ label, href }) => (
                <a
                  key={label}
                  href={href}
                  onClick={e => { e.preventDefault(); navigate('/about'); }}
                  style={{ color: '#475569', fontSize: 12, textDecoration: 'none', cursor: 'pointer' }}
                  onMouseEnter={e => e.target.style.color = '#94a3b8'}
                  onMouseLeave={e => e.target.style.color = '#475569'}
                >
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
