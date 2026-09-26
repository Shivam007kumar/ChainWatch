import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LandingPage       from './pages/LandingPage';
import DashboardPage     from './pages/DashboardPage';
import InvestigationPage from './pages/InvestigationPage';
import AlertsPage        from './pages/AlertsPage';
import SearchPage        from './pages/SearchPage';
import IngestPage        from './pages/IngestPage';
import AboutPage         from './pages/AboutPage';
import Workspace         from './Workspace';   // legacy — kept, not linked from nav

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/"                      element={<LandingPage />} />
        <Route path="/dashboard"             element={<DashboardPage />} />
        <Route path="/investigate"           element={<InvestigationPage />} />
        <Route path="/investigate/:address"  element={<InvestigationPage />} />
        <Route path="/alerts"                element={<AlertsPage />} />
        <Route path="/search"                element={<SearchPage />} />
        <Route path="/ingest"                element={<IngestPage />} />
        <Route path="/about"                 element={<AboutPage />} />
        <Route path="/workspace"             element={<Workspace />} />
      </Routes>
    </Router>
  );
}
