# Estacle Node.js offline-first CRM

## Run locally
```bash
cd server
npm install
npm start
```
Open http://localhost:5001

Demo login: `admin@estacle.com` / `admin123`

## Offline
1. Sign in while online (data downloads to IndexedDB)
2. Turn off network
3. Full dashboard still works from local data
4. Creates queue locally and sync when back online
