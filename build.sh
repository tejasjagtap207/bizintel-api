#!/bin/bash
# build.sh — Render runs this when deploying your app

# Install dependencies
pip install -r requirements.txt

# Create database tables
python -c "from config import DATABASE_URL; from database import engine, metadata; metadata.create_all(engine); print('✅ Database tables created')"

echo "✅ Build complete! Starting server..."