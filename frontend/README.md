# Frontend

React + Vite application for K-12 AI Legislative Map dashboard.

## Setup

### With Docker
```bash
docker-compose up frontend
```

### Manual Setup
```bash
npm install
npm run dev
```

App will be available at http://localhost:5173

## Project Structure

```
src/
├── App.jsx              # Main app component
├── App.css              # App styles
├── main.jsx             # Entry point
├── index.css            # Global styles
└── components/
    ├── Dashboard.jsx    # Summary stats & filters
    ├── Map.jsx          # State grid (placeholder for SVG)
    └── StateModal.jsx   # Detailed state info modal
```

## Features

- **Dashboard**: Summary statistics and filtering by stance/maturity
- **State Grid**: Interactive grid showing all states with their regulatory stance
- **State Modal**: Detailed legislation and guidance info when clicking a state
- **Responsive**: Works on desktop, tablet, and mobile

## Next Steps

1. Replace state grid with interactive SVG map
2. Add timeline view
3. Add comparison feature
4. Add export functionality
