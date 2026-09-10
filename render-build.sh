#!/usr/bin/env bash
# exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Install Playwright browsers inside the project directory so Render doesn't delete them
export PLAYWRIGHT_BROWSERS_PATH=0
playwright install chromium
