/**
 * Badge Overlay + Accessibility Tree Extraction
 * 
 * Wrapped in IIFE for Playwright evaluate() compatibility.
 */

(function() {
  const BADGE_STYLE = `
    position: absolute !important;
    z-index: 999999 !important;
    background: rgba(255, 68, 68, 0.9) !important;
    color: white !important;
    font-size: 12px !important;
    font-weight: bold !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    pointer-events: none !important;
    line-height: 1.2 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
    font-family: monospace !important;
    white-space: nowrap !important;
  `;

  const SELECTOR = [
    'a[href]:not([href^="javascript:"])',
    'button:not([disabled])',
    'input:not([type="hidden"]):not([disabled])',
    'textarea:not([disabled])',
    'select:not([disabled])',
    '[role="button"]:not([aria-disabled="true"])',
    '[role="link"]',
    '[role="menuitem"]',
    '[role="tab"]',
    '[role="checkbox"]',
    '[role="radio"]',
    '[role="combobox"]',
    '[onclick]',
    '[tabindex="0"]',
  ].join(', ');

  function getA11yInfo(el) {
    const role = el.getAttribute('role') || el.tagName.toLowerCase();
    const text = (el.textContent || '').trim().slice(0, 100);
    const ariaLabel = el.getAttribute('aria-label') || '';
    const name = el.getAttribute('name') || '';
    const placeholder = el.placeholder || '';
    const title = el.getAttribute('title') || '';
    
    const label = ariaLabel || text || name || placeholder || title || role;
    const type = el.type || '';
    
    let desc = role;
    if (type && type !== 'text') desc += ' type="' + type + '"';
    if (label) desc += ' "' + label + '"';
    
    return desc;
  }

  function removeBadges() {
    document.querySelectorAll('.vision-badge-overlay').forEach(el => el.remove());
    document.querySelectorAll('.vision-badge-marker').forEach(el => el.remove());
  }

  function generateSelector(el, num) {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.hasAttribute('name')) return '[name="' + CSS.escape(el.getAttribute('name')) + '"]';
    if (el.getAttribute('aria-label')) return '[aria-label="' + el.getAttribute('aria-label') + '"]';
    if (el.hasAttribute('placeholder')) return '[placeholder="' + el.getAttribute('placeholder') + '"]';
    if (el.hasAttribute('data-testid')) return '[data-testid="' + el.getAttribute('data-testid') + '"]';
    return '.vision-badge-marker[data-badge-num="' + num + '"]';
  }

  function badgeElements() {
    removeBadges();
    
    const elements = Array.from(document.querySelectorAll(SELECTOR));
    const badges = [];
    const seen = new Set();
    
    elements.forEach((el, idx) => {
      if (seen.has(el) || el.offsetWidth === 0 || el.offsetHeight === 0) return;
      seen.add(el);
      
      const num = badges.length + 1;
      const a11y = getA11yInfo(el);
      const selector = generateSelector(el, num);
      
      badges.push({ num: num, selector: selector, a11y: a11y });
      
      const badge = document.createElement('div');
      badge.className = 'vision-badge-marker';
      badge.setAttribute('data-badge-num', String(num));
      badge.setAttribute('style', BADGE_STYLE);
      badge.textContent = String(num);
      
      const rect = el.getBoundingClientRect();
      const scrollX = window.scrollX;
      const scrollY = window.scrollY;
      
      badge.style.left = (rect.left + scrollX) + 'px';
      badge.style.top = (rect.top + scrollY - 16) + 'px';
      
      document.body.appendChild(badge);
    });
    
    return badges;
  }

  function extractA11yTree() {
    const lines = [];
    
    function walk(node, depth) {
      if (node.offsetWidth === 0 && node.offsetHeight === 0) return;
      
      const a11y = getA11yInfo(node);
      const indent = '  '.repeat(depth);
      
      if (depth > 0) {
        lines.push(indent + '- ' + a11y);
      }
      
      for (const child of Array.from(node.children)) {
        walk(child, depth + 1);
      }
    }
    
    walk(document.body, 0);
    return lines.slice(0, 200).join('\n');
  }

  // Execute and return results
  return {
    badges: badgeElements(),
    a11yTree: extractA11yTree(),
    url: window.location.href,
    title: document.title,
  };
})();
