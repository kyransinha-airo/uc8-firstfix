# Frontend

React 18 + Vite + Tailwind 4. Dev server on port **3008**, proxying `/api` to the backend
on 8008 (set `VITE_API_TARGET` to point elsewhere). Deployed to Azure Static Web Apps.

```bash
npm install
npm run dev     # http://localhost:3008, needs the backend
npm run build   # type-check + production build into dist/
```

| Path | Purpose |
| --- | --- |
| `src/App.tsx` | The page (placeholder until the five screens land) |
| `src/api/` | Fetch wrapper and backend calls |
| `src/index.css` | Tailwind theme: Airo brand colours, fonts, shared utilities |
