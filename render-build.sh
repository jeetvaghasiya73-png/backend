#!/usr/bin/env bash
# exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Install Playwright browsers for Linux (Dependencies are already in Render OS)
playwright install chromium
