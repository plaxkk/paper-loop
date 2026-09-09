#!/usr/bin/env python3
"""
Analytics module for paper-to-wechat-pipeline.
Handles DB schema, data collection, user profiling, and weekly strategy.
"""
from .schema import init_db, parse_content_analysis, parse_user_analysis, store_parsed, stats
from .collector import start_collector
from .profile import generate_profile
from .strategy import generate_strategy
