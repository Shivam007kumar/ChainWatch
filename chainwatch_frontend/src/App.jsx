import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './Home';
import Workspace from './Workspace';

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/workspace" element={<Workspace />} />
      </Routes>
    </Router>
  );
}