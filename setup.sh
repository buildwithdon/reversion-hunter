#!/bin/bash

# Setup script for Reversion Hunter deployment

echo "Setting up Reversion Hunter..."

# Create data directories
mkdir -p data/cache
mkdir -p logs

# Install system dependencies (for TA-Lib if needed)
# Uncomment if deploying to cloud that needs TA-Lib
# apt-get update
# apt-get install -y build-essential wget
# wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
# tar -xzf ta-lib-0.4.0-src.tar.gz
# cd ta-lib/
# ./configure --prefix=/usr
# make
# make install
# cd ..

echo "Setup complete!"
echo "Run 'streamlit run app/main.py' to start the application"
