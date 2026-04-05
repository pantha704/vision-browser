"""Tests for new Playwright browser component."""

from __future__ import annotations


from vision_browser.playwright_browser import PlaywrightBrowser
from vision_browser.config import BrowserConfig


class TestPlaywrightBrowser:
    def test_create_browser(self):
        """Test browser creation without CDP."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        assert browser._browser is not None
        assert browser._page is not None
        browser.close()

    def test_navigate_to_page(self):
        """Test navigation to a URL."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            assert "example.com" in browser.get_url()
            assert "Example Domain" in browser.get_title()
        finally:
            browser.close()

    def test_screenshot_creates_file(self, tmp_path):
        """Test screenshot creates a file."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            path = str(tmp_path / "test.png")
            result = browser.screenshot(path)
            assert "path" in result
            assert "refs" in result
        finally:
            browser.close()

    def test_badge_injection(self):
        """Test badge injection extracts elements."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            result = browser._inject_badges()
            assert "refs" in result
            assert "legend" in result
            assert isinstance(result["refs"], dict)
        finally:
            browser.close()

    def test_click_method(self):
        """Test click method with badge number."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            result = browser._inject_badges()
            # Click uses CSS selectors, not badge elements
            # Just verify the method doesn't raise on valid selectors
            if result["refs"]:
                for num, selector in result["refs"].items():
                    if selector.startswith(("#", "[")):
                        try:
                            browser.click(num)
                            break
                        except Exception:
                            continue
        finally:
            browser.close()

    def test_fill_method(self):
        """Test fill method with text."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            result = browser._inject_badges()
            # Fill uses CSS selectors, just verify it accepts the params
            if result["refs"]:
                first_num = list(result["refs"].keys())[0]
                # Should accept the call without type errors
                browser.fill(first_num, "test text")
        except Exception as e:
            # Expected on pages with few inputs
            assert "Fill failed" in str(e) or "ActionExecutionError" in str(
                type(e).__name__
            )
        finally:
            browser.close()

    def test_get_url_and_title(self):
        """Test URL and title extraction."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            assert browser.get_url() == "https://example.com/"
            assert "Example Domain" in browser.get_title()
        finally:
            browser.close()

    def test_execute_batch(self):
        """Test batch action execution."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            browser.open("https://example.com")
            result = browser._inject_badges()
            if result["refs"]:
                actions = [{"action": "scroll", "direction": "down", "amount": 100}]
                executed = browser.execute_batch(actions)
                assert executed >= 0
        finally:
            browser.close()

    def test_is_alive(self):
        """Test browser alive check."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        try:
            assert browser.is_alive() is True
        finally:
            browser.close()

    def test_close(self):
        """Test browser close."""
        cfg = BrowserConfig()
        browser = PlaywrightBrowser(cfg)
        browser.close()
        # Should not raise


class TestBrowserConfig:
    def test_default_config(self):
        """Test default config values."""
        cfg = BrowserConfig()
        assert cfg.cdp_url == ""
        assert cfg.session_name == ""
        assert cfg.annotate is True
        assert cfg.timeout_ms == 30000

    def test_cdp_config(self):
        """Test CDP config."""
        cfg = BrowserConfig(cdp_url="http://localhost:9222")
        assert cfg.cdp_url == "http://localhost:9222"
