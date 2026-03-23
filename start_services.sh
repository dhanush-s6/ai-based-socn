#!/bin/bash
# Quick launcher for LTE-AI-SON services - TERMINAL MODE
# This script opens 3 terminals for AI Server, Dashboard, and NS-3

cd "$(dirname "$0")"
python3 start_all_services.py
