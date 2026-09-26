/**
 * CwNav.jsx
 * ─────────
 * Shared top navigation used across all ChainWatch pages.
 * Visual language: gov-blue background, 4px saffron border-bottom,
 * white text, subtle highlight for active route.
 *
 * Props:
 *   status  'ok' | 'err' | 'checking'  — backend health dot
 */
import { useNavigate } from 'react-router-dom';

const NAV_LINKS = [
  { label: 'Dashboard',   href: '/dashboard' },
  { label: 'Investigate', href: '/investigate' },
  { label: 'Alerts',      href: '/alerts' },
  { label: 'Search',      href: '/search' },
  { label: 'Ingest',      href: '/ingest' },
  { label: 'About',       href: '/about' },
];

export default function CwNav({ status = 'ok' }) {
  const navigate = useNavigate();
  const path     = window.location.pathname;

  const isActive = (href) => {
    // exact match for dashboard to avoid '/dashboard' activating on '/dashboard/...'
    if (href === '/dashboard') return path === '/dashboard';
    return path.startsWith(href);
  };

  return (
    <header className="topbar">
      {/* Brand — clicking takes you to landing page */}
      <div
        className="topbar-brand"
        onClick={() => navigate('/')}
        style={{ cursor: 'pointer' }}
      >
        <img
          src="/emblem_india.svg"
          alt="Emblem of India"
          style={{ height: 38, filter: 'brightness(0) invert(1)' }}
        />
        <div className="brand-titles">
          <div className="brand-goi">Government of India</div>
          <div className="brand-name">ChainWatch</div>
        </div>
      </div>

      <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {NAV_LINKS.map(({ label, href }) => {
          const active = isActive(href);
          return (
            <button
              key={href}
              onClick={() => navigate(href)}
              style={{
                background:    active ? 'rgba(255,255,255,0.15)' : 'transparent',
                border:        active ? '1px solid rgba(255,255,255,0.3)' : '1px solid transparent',
                color:         active ? '#ffffff' : 'rgba(255,255,255,0.75)',
                padding:       '5px 11px',
                borderRadius:  '3px',
                fontSize:      '12px',
                fontWeight:    700,
                cursor:        'pointer',
                fontFamily:    'inherit',
                letterSpacing: '0.03em',
                transition:    'all 0.12s',
              }}
            >
              {label}
            </button>
          );
        })}
      </nav>

      <div className="topbar-actions">
        <div
          className="shield-status"
          style={{
            background:  status === 'ok'  ? 'rgba(19,136,8,0.15)'  : 'rgba(204,0,0,0.15)',
            borderColor: status === 'ok'  ? 'var(--gov-green)'      : 'var(--gov-red)',
            color:       status === 'ok'  ? '#a7f3d0'               : '#fca5a5',
          }}
        >
          <span style={{
            display:    'inline-block',
            width:       7,
            height:      7,
            borderRadius:'50%',
            background: 'currentColor',
            marginRight: 4,
            animation:  status === 'ok' ? 'pulseShield 2s infinite' : 'none',
          }} />
          {status === 'ok'       ? 'BACKEND ONLINE'  :
           status === 'err'      ? 'BACKEND OFFLINE' :
                                   'CHECKING…'}
        </div>
      </div>
    </header>
  );
}
