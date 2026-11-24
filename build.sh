#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "=================================================="
echo " CivicAI - Render Production Build Script"
echo "=================================================="

# 1. Build frontend React SPA
echo "===> Step 1: Installing frontend dependencies and building SPA..."
cd frontend
npm install
npm run build
cd ..

# 2. Upgrade pip and install CPU-only torch to prevent Render OOM / disk overflow
echo "===> Step 2: Installing CPU PyTorch (fast & low memory)..."
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. Install backend Python dependencies
echo "===> Step 3: Installing backend requirements..."
pip install -r backend/requirements.txt

echo "===> Build completed successfully!"
