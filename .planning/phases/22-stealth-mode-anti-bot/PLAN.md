# Phase 22: Stealth Mode for Anti-Bot

## Problem
X/Twitter login fails because overlay divs (`#layers`) intercept pointer events on form inputs. Playwright's `click()` and `fill()` trigger real browser events that anti-bot systems detect and block.

## Root Cause (from logs)
```
<div class="css-175oi2r">…</div> from <div id="layers"> intercepts pointer events
<input name="text" type="text"/> from <div id="layers"> intercepts pointer events
```

## Solution
1. **Direct DOM dispatch** — bypass pointer events by dispatching input/keyboard events directly on the element, not through click()
2. **Stealth plugin** — use `playwright-stealth` (already installed) to remove automation fingerprints
3. **Human-like timing** — random delays between keystrokes (50-200ms)
4. **Focus + type pattern** — focus element via JS, then dispatch KeyboardEvent for each char

## Files Changed
- `src/vision_browser/playwright_browser.py` — add `stealth_fill()`, `stealth_click()` methods
- `src/vision_browser/playwright_browser.py` — enable stealth on browser launch
- `src/vision_browser/config.py` — add `stealth_mode: bool = True`

## Verification
- X/Twitter login completes successfully
- YouTube search still works
- No regression on non-SPA sites
- 240 tests still pass
