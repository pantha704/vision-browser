# Phase 18: Rate Limit Persistence

## Goal
Persist rate limit delay state across runs so the tool doesn't hit API limits immediately after restart.

## Current State
- `_last_request_time` is an instance variable (lost on restart)
- `_rate_delay` is hardcoded from config (0.5s default)
- No mechanism to remember "we just hit the API, wait X seconds"

## Implementation
1. Add `rate_limit_state.json` file in session dir
2. Save `_last_request_time` on every API call
3. Load on VisionClient init, apply remaining delay if needed
4. File format: `{"last_request_time": float, "current_delay": float}`

## Files Changed
- `src/vision_browser/vision.py` — load/save rate limit state
- `src/vision_browser/config.py` — add rate_limit_state_path

## Verification
- After API call, state file exists with timestamp
- On restart, if < rate_delay seconds elapsed, waits remaining time
- No state file on fresh start (no delay)
