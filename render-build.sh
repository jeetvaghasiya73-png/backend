#!/usr/bin/env bash
# exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Install Playwright browsers and dependencies for Linux
playwright install chromium
playwright install-deps chromium
