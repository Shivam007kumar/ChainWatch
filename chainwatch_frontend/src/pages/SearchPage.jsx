/**
 * SearchPage.jsx — /search
 * ────────────────────────
 * Global search using GET /api/v1/search (frozen endpoint).
 * Minimum 4 characters, searches wallet / transaction / IP.
 * Results click through to /investigate/:address (wallet),
 * or directly into investigation for tx/ip.
 */
import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import CwNav                             from '../components/CwNav';
import { search }                        from '../api/search';

const TYPE_LABEL = {
  wallet:      'Wallet',
  transaction: 'TX',
  ip:          'IP',
};

export default function SearchPage() {
  const navigate                   = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQ                   = searchParams.get('q') ?? '';

  const [query,   setQuery]   = useState(initialQ);
  const [results, setResults] = useState(null);   // null = not searched yet
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [types,   setTypes]   = useState(['wallet', 'transaction', 'ip']);
  const inputRef              = useRef(null);

  // Run search when query param changes (e.g. arriving with ?q=...)
  useEffect(() => {
    if (initialQ.length >= 4) runSearch(initialQ);
    inputRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSearch = (q) => {
    if (!q || q.length < 4) return;
    setLoading(true);
    setError(null);
    setSearchParams({ q });
    search(q, types, 30)
      .then(data => { setResults(data.results ?? []); setLoading(false); })
      .catch(err  => { setError(err.detail ?? err.message ?? 'Search failed.'); setLoading(false); });
  };

  const handleInput = (e) => {
    const v = e.target.value;
    setQuery(v);
    if (v.length >= 4) runSearch(v);
    else if (v.length === 0) setResults(null);
  };

  const handleResultClick = (result) => {
    if (result.type === 'wallet') {
      navigate(`/investigate/${encodeURIComponent(result.id)}`);
    } else if (result.type === 'transaction') {
      navigate(`/investigate?tx=${encodeURIComponent(result.id)}`);
    } else if (result.type === 'ip') {
      navigate(`/investigate?ip=${encodeURIComponent(result.id)}`);
    }
  };

  const toggleType = (t) => {
    setTypes(prev =>
      prev.includes(t)
        ? prev.filter(x => x !== t)
        : [...prev, t]
    );
    if (query.length >= 4) setTimeout(() => runSearch(query), 0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: '#f8fafc' }}>
      <CwNav status="ok" />

      <div className="search-page">

        {/* ── Search input ── */}
        <div className="search-input-wrap">
          <span style={{ color: '#94a3b8', fontSize: 14, flexShrink: 0 }}>🔍</span>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search wallet address, transaction ID, or IP…  (min 4 chars)"
            value={query}
            onChange={handleInput}
            onKeyDown={e => e.key === 'Enter' && runSearch(query)}
            autoFocus
          />
          {loading && (
            <div className="inv-spinner" style={{ marginLeft: 6 }} />
          )}
        </div>

        {/* ── Type filter chips ── */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
          {['wallet', 'transaction', 'ip'].map(t => (
            <button
              key={t}
              onClick={() => toggleType(t)}
              style={{
                padding: '3px 10px',
                borderRadius: 2,
                border: '1px solid',
                fontSize: 10,
                fontWeight: 800,
                cursor: 'pointer',
                fontFamily: 'inherit',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                background:   types.includes(t) ? (
                  t === 'wallet'      ? 'var(--gov-saffron-dim)' :
                  t === 'transaction' ? 'var(--gov-blue-dim)'    :
                                       'var(--gov-green-dim)'
                ) : '#f1f5f9',
                borderColor: types.includes(t) ? (
                  t === 'wallet'      ? 'var(--gov-saffron)' :
                  t === 'transaction' ? 'var(--gov-blue)'    :
                                       'var(--gov-green)'
                ) : '#cbd5e1',
                color: types.includes(t) ? (
                  t === 'wallet'      ? '#92400e'           :
                  t === 'transaction' ? 'var(--gov-blue)'   :
                                       'var(--gov-green)'
                ) : '#64748b',
              }}
            >
              {TYPE_LABEL[t]}
            </button>
          ))}
        </div>

        {/* ── Error ── */}
        {error && (
          <div style={{ color: 'var(--gov-red)', fontSize: 12, marginBottom: 16 }}>⚠ {error}</div>
        )}

        {/* ── Prompt ── */}
        {results === null && !loading && (
          <div style={{ color: '#94a3b8', fontSize: 13 }}>
            Enter at least 4 characters to search.
          </div>
        )}

        {/* ── No results ── */}
        {results?.length === 0 && !loading && (
          <div style={{ color: '#64748b', fontSize: 13 }}>
            No results found for <strong>"{query}"</strong>.
          </div>
        )}

        {/* ── Results ── */}
        {results && results.length > 0 && (
          <>
            <div style={{ fontSize: 10, fontWeight: 800, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
              {results.length} result{results.length !== 1 ? 's' : ''}
            </div>
            {results.map((result, i) => {
              const riskColor = result.risk_score >= 70 ? 'var(--gov-red)'
                              : result.risk_score >= 40 ? '#c2410c'
                              : '#22c55e';
              return (
                <div
                  key={i}
                  className="search-result"
                  onClick={() => handleResultClick(result)}
                >
                  <span className={`search-result__type search-result__type--${result.type}`}>
                    {TYPE_LABEL[result.type] ?? result.type}
                  </span>
                  <span className="search-result__id">
                    {result.label ?? result.id}
                  </span>
                  {result.state && (
                    <span style={{ fontSize: 10, color: '#64748b', flexShrink: 0 }}>
                      {result.state}
                    </span>
                  )}
                  {result.risk_score > 0 && (
                    <span
                      className="search-result__risk"
                      style={{ color: riskColor }}
                    >
                      {Math.round(result.risk_score)}%
                    </span>
                  )}
                  {result.flagged && (
                    <span style={{ fontSize: 9, color: 'var(--gov-red)', fontWeight: 800, flexShrink: 0 }}>
                      ⚠ FLAGGED
                    </span>
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
