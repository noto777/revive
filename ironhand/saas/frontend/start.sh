#!/bin/bash
cd /root/.openclaw/workspace-personal/ironhand/saas/frontend

if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

echo "Starting frontend on port 3001..."
npm run dev
