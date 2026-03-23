#!/bin/bash
# Quick launcher for LTE-AI-SON services - BACKGROUND MODE
# This script runs AI Server, Dashboard, and NS-3 as background processes

cd "$(dirname "$0")"
python3 start_services_background.py "$@"
