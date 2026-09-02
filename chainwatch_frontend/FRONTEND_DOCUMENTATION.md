# ChainWatch Frontend Documentation

## Overview
ChainWatch is an offline Bitcoin intelligence platform built with React and Vite. The frontend provides a comprehensive dashboard for analyzing blockchain transactions, detecting anomalies, and visualizing entity correlations through interactive graphs and charts.

---

## Project Structure

```
chainwatch_frontend/
├── .agents/                    # Kiro AI agent configurations
│   └── skills/
│       └── ux4g-design/       # UX design skill for agent
├── public/                     # Static assets
│   ├── favicon.svg            # Browser tab icon
│   └── icons.svg              # SVG icon sprite
├── src/                        # Source code
│   ├── assets/                # Image and media assets
│   ├── components/            # React components
│   ├── App.jsx                # Root application component
│   ├── index.css              # Global styles
│   ├── main.jsx               # Application entry point
│   ├── main.ts                # TypeScript entry (unused)
│   ├── counter.ts             # Utility file (unused)
│   └── style.css              # Additional styles (unused)
├── .gitignore                 # Git ignore rules
├── index.html                 # HTML entry point
├── package.json               # Dependencies and scripts
├── tsconfig.json              # TypeScript configuration
└── vite.config.js             # Vite bundler configuration
```

---

## Core Files

### Configuration Files

#### `package.json`
**Purpose:** Defines project metadata, dependencies, and npm scripts.

**Key Dependencies:**
- **react** (^19.2.8): UI library
- **react-dom** (^19.2.8): React rendering for web
- **react-force-graph-2d** (^1.29.1): Interactive force-directed graph visualization
- **recharts** (^3.10.1): Charting library for data visualization

**Dev Dependencies:**
- **vite** (^8.2.2): Fast build tool and dev server
- **@vitejs/plugin-react** (^6.1.1): React plugin for Vite
- **typescript** (~6.0.2): Type checking

**Scripts:**
- `npm run dev`: Start development server
- `npm run build`: Build production bundle
- `npm run preview`: Preview production build locally

---

#### `vite.config.js`
**Purpose:** Configures the Vite build tool.

**Configuration:**
- **Plugins:** React plugin for JSX transformation
- **Server Port:** 5173
- **Auto-open:** Opens browser automatically on dev server start

---

#### `tsconfig.json`
**Purpose:** TypeScript compiler configuration.

**Key Settings:**
- **Target:** ES2023 modern JavaScript
- **Module:** ESNext for modern module syntax
- **Bundler mode:** Optimized for Vite
- **No emit:** Type checking only (Vite handles building)
- **Strict linting:** Enforces unused variable/parameter detection

---

#### `.gitignore`
**Purpose:** Specifies files and directories to exclude from version control.

**Excluded:**
- `node_modules/`: Dependencies
- `dist/`: Build output
- Log files and IDE settings
- OS-specific files (.DS_Store)

---

### HTML & Entry Points

#### `index.html`
**Purpose:** Root HTML template and application entry point.

**Features:**
- Defines document metadata and viewport settings
- Loads Google Fonts (Inter for UI, JetBrains Mono for code)
- Contains `<div id="root">` mount point for React
- Loads main.jsx as module script

---

#### `src/main.jsx`
**Purpose:** JavaScript entry point that bootstraps the React application.

**Functionality:**
- Creates React root from DOM element with id "root"
- Wraps `<App>` in `<React.StrictMode>` for development warnings
- Imports global styles from index.css

---

### Application Components

#### `src/App.jsx`
**Purpose:** Root React component that orchestrates the entire dashboard.

**Key Features:**

1. **API Integration:**
   - Custom `useAPI` hook for data fetching from backend (`http://localhost:8000/api/v1`)
   - Fetches stats, anomalies, clusters, and graph data
   - Handles loading and error states

2. **State Management:**
   - `highlightedWallet`: Currently selected wallet for cross-component highlighting
   - `minConfidence`: Filter threshold for anomaly confidence scores
   - `selectedCluster`: Active cluster filter

3. **Component Structure:**
   - **Topbar:** Navigation bar with branding, status, and alert count
   - **MetricCards:** Key statistics overview
   - **ChartsView:** Donut and bar charts for analytics
   - **GraphView:** Interactive force-directed entity correlation graph
   - **AlertTable:** Filterable list of flagged entities with details
   - **Footer:** Technical stack and version information

4. **Data Flow:**
   - Filters alerts client-side based on confidence and cluster
   - Passes selected wallet to graph for highlighting
   - Coordinates state between AlertTable and GraphView

---

#### `src/components/MetricCards.jsx`
**Purpose:** Displays key metrics as animated stat cards.

**Features:**
- Shows 5 core metrics: transactions, wallets, anomalies, high-risk wallets, clusters
- **Custom Hook (`useCountUp`)**: Animates numbers from 0 to target value
- Color-coded cards (teal, blue, amber, red, purple)
- Loading skeleton states while data fetches
- Icons and subtitles for context

**Metrics:**
1. **Transactions Analyzed:** Total synthetic BTC transactions
2. **Unique Wallets:** Number of addresses observed
3. **Anomalies Detected:** Flagged by Isolation Forest ML model (8% rate)
4. **High-Risk Wallets:** Confidence ≥ 85%
5. **Entity Clusters:** K-Means clustering results (k=6)

---

#### `src/components/ChartsView.jsx`
**Purpose:** Visualizes analytics through charts using Recharts library.

**Charts:**

1. **Risk Distribution (Donut Chart):**
   - Shows normal vs flagged wallet ratio
   - Interactive tooltips with percentages
   - Color-coded (teal for normal, red for flagged)

2. **Anomalies by Pattern (Bar Chart):**
   - Displays wallet count per cluster
   - Cluster names shortened for readability
   - Custom tooltips with full cluster names
   - Blue bars with rounded tops

**Styling:**
- Custom tooltip component with shadowed white background
- Legends with color-coded dots
- Responsive containers that adapt to screen size

---

#### `src/components/GraphView.jsx`
**Purpose:** Renders interactive force-directed graph of entity relationships.

**Features:**

1. **Node Types & Colors:**
   - **IP Nodes:** Blue (#3b82f6) / Red when flagged (#ef4444)
   - **Transactions:** Purple (#a855f7) / Light purple when flagged (#c084fc)
   - **Wallets:** Teal (#00d4aa) / Pink when flagged (#ff4d6d)

2. **Link Types & Colors:**
   - **BROADCASTED:** Blue (59, 130, 246, 0.3) - IP broadcasting transaction
   - **SENT_TO_NODE:** Light blue - Transaction sent to node
   - **INPUT_TO_TX:** Teal - Wallet input to transaction
   - **OUTPUT_TO_WALLET:** Purple - Transaction output to wallet

3. **Interactive Behaviors:**
   - **Hover:** Shows node labels with type and ID
   - **Highlight:** Dims non-neighbor nodes when wallet selected
   - **Zoom & Center:** Auto-centers on highlighted wallet
   - **Directional Particles:** Animated particles show transaction flow direction

4. **Physics:**
   - D3 force simulation with -60 charge strength
   - 120 cooldown ticks for stable layout
   - Node size varies by type and flagged status

---

#### `src/components/AlertTable.jsx`
**Purpose:** Displays filterable, sortable list of flagged wallet addresses.

**Features:**

1. **Filter Controls:**
   - **Confidence slider:** 0-100% threshold
   - **Cluster buttons:** Filter by specific pattern or "All Patterns"
   - Dynamic count display

2. **Alert Row Display:**
   - Rank number and cluster name
   - Truncated wallet address with copy-to-clipboard button
   - Confidence score as animated progress bar
   - Color-coded by severity (high ≥85%, mid ≥72%, low <72%)
   - Cluster badge with color coding

3. **Detail Drawer (Expandable):**
   - **Intelligence Report:** AI-generated reason for flagging
   - **Statistics Grid:**
     - Transaction count
     - Total BTC volume
     - Unique IP count
     - High-risk connection hits
     - Sample transaction ID

4. **Interactions:**
   - Click row to expand/collapse details
   - Click cluster badges to filter
   - Copy wallet address to clipboard
   - Selected row highlights and notifies GraphView

**Styling:**
- Selected rows get teal background with left border
- Hover states for better UX
- Responsive scrollable container

---

### Styling

#### `src/index.css`
**Purpose:** Global CSS styles and design system for the entire application.

**Design System:**

1. **CSS Variables (`:root`):**
   - **Colors:** Teal (primary), red (alerts), amber (warnings), blue (info), purple (clusters)
   - **Backgrounds:** Primary (#f3f4f6), secondary (white), card (white)
   - **Text:** Primary (#111827), secondary (#374151), muted (#6b7280)
   - **Fonts:** Inter (UI), JetBrains Mono (monospace/code)
   - **Spacing:** Border radius (12px cards, 8px small), shadows

2. **Layout Classes:**
   - `.app-shell`: Full viewport flex container
   - `.topbar`: Sticky navigation bar (64px height)
   - `.main-content`: Centered content area (max-width 1600px)
   - `.dashboard-grid.two-column`: Graph + Alert side-by-side layout

3. **Component Styles:**
   - **Metric Cards:** Color-coded with left border accent
   - **Graph Card:** 600px height with radial gradient background
   - **Alert Panel:** Scrollable with hover states
   - **Charts:** Responsive containers with custom legends

4. **Animations:**
   - **Pulse dot:** Status indicator animation
   - **Shimmer:** Loading skeleton effect
   - **Spin:** Loading spinner rotation
   - **Slide-down:** Drawer expand animation

5. **Responsive Design:**
   - Grid adapts to single column below 1200px
   - Auto-fit grids for metric cards and charts

---

## Additional Files

### `src/assets/`
Contains image assets:
- `hero.png`: Hero/banner image
- `vite.svg`, `typescript.svg`: Technology logos

### `public/`
Static files served directly:
- `favicon.svg`: Browser tab icon
- `icons.svg`: SVG sprite for icons

### Unused Files
- `src/main.ts`: TypeScript entry point (not used, JSX version active)
- `src/counter.ts`: Utility file (unused)
- `src/style.css`: Additional styles (unused, all styles in index.css)

---

## Data Flow

```
Backend API (localhost:8000/api/v1)
    ↓
App.jsx (useAPI hook)
    ↓
├─→ MetricCards.jsx      (stats)
├─→ ChartsView.jsx       (stats, clusters)
├─→ GraphView.jsx        (graphData, highlightedWallet)
└─→ AlertTable.jsx       (alerts, clusters, filters)
    ↓
User interactions
    ↓
State updates in App.jsx
    ↓
Re-render affected components
```

---

## API Endpoints Used

1. **`/api/v1/stats`**: Overall statistics (transaction count, wallet count, anomaly count)
2. **`/api/v1/anomalies?limit=50`**: List of flagged wallets with confidence scores
3. **`/api/v1/clusters`**: Cluster information from K-Means analysis
4. **`/api/v1/graph`**: Graph nodes and links for visualization

---

## Development Workflow

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start dev server:**
   ```bash
   npm run dev
   ```
   Opens browser at `http://localhost:5173`

3. **Build for production:**
   ```bash
   npm run build
   ```
   Creates optimized bundle in `dist/`

4. **Preview production build:**
   ```bash
   npm run preview
   ```

---

## Key Technologies

- **React 19.2.8:** Component-based UI framework
- **Vite 8.2.2:** Next-generation frontend tooling
- **React Force Graph 2D:** WebGL-powered graph visualization
- **Recharts:** Declarative charting library
- **CSS Custom Properties:** Design system variables
- **Google Fonts:** Inter + JetBrains Mono

---

## Architecture Decisions

1. **No state management library:** Uses React's built-in hooks for simplicity
2. **Client-side filtering:** Reduces backend load, instant UI updates
3. **Custom hooks:** `useAPI` and `useCountUp` for reusable logic
4. **Single CSS file:** All styles in index.css for easy maintenance
5. **Offline-first:** All data pre-processed, no real-time connections
6. **Component isolation:** Each component is self-contained and reusable

---

## Performance Optimizations

- **Vite's fast HMR:** Instant hot module replacement during development
- **Lazy animations:** Count-up effects only animate visible metrics
- **Memoized graph data:** useMemo for neighbor calculations
- **Responsive containers:** Charts adapt to container size automatically
- **Cooldown ticks:** Graph simulation stabilizes efficiently

---

## Browser Compatibility

- Modern browsers supporting ES2023
- CSS Grid and Flexbox required
- WebGL for graph rendering
- No IE11 support

---

## Future Enhancements Possible

- Real-time WebSocket updates for live data
- Advanced filtering (date ranges, transaction amounts)
- Export functionality (CSV, PDF reports)
- Dark mode theme toggle
- Multi-language support
- Keyboard shortcuts and accessibility improvements
- Graph layout persistence (save custom arrangements)

---

## Troubleshooting

**Port 5173 already in use:**
```bash
# Kill process using port 5173
lsof -ti:5173 | xargs kill -9
```

**Backend not responding:**
- Ensure backend is running on `http://localhost:8000`
- Check CORS settings if requests fail

**Graph not rendering:**
- Check browser console for WebGL errors
- Ensure graph data has valid nodes and links structure

---

*Last Updated: September 1, 2026*
*Version: 1.0*
