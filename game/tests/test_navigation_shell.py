"""Global navigation is additive, accessible and preserves server actions."""
import re
from pathlib import Path
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase


class NavigationShellTests(SimpleTestCase):
    def render_shell(self, superuser=False):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=False, is_superuser=superuser)
        request.resolver_match = SimpleNamespace(url_name="home")
        return render_to_string("base.html", {
            "request": request, "csrf_token": "navigation-test-csrf",
            "current_manager": {
                "club_url": "/clubs/13/", "squad_url": "/clubs/13/squad/",
                "tactics_url": "/clubs/13/tactics/",
            },
        })

    def test_early_script_and_paired_cache_versions(self):
        html = self.render_shell()
        script = re.search(r'navigation-shell\.js\?v=([^"]+)', html)
        self.assertIsNotNone(script)
        self.assertLess(script.start(), html.index('rel="stylesheet"'))
        self.assertIn(f"navigation-shell.css?v={script.group(1)}", html)
        self.assertNotIn('defer src=', html.split("navigation-shell.js")[0])

    def test_actions_labels_active_link_and_csrf_are_retained(self):
        html = self.render_shell()
        self.assertIn('id="nav-toggle"', html)
        self.assertIn('aria-expanded="true"', html)
        self.assertIn('aria-controls="main-navigation"', html)
        self.assertIn('href="/" aria-current="page"', html)
        self.assertIn('<span class="nav-label">Übersicht</span>', html)
        self.assertIn('href="/handbuch/"', html)
        self.assertIn('action="/clubs/" method="get" role="search"', html)
        self.assertIn('id="nav-search-open"', html)
        logout = html.split('class="nav-logout-form"')[1].split("</form>")[0]
        self.assertIn('method="post"', logout)
        self.assertIn('name="csrfmiddlewaretoken" value="navigation-test-csrf"', logout)
        self.assertIn('type="submit"', logout)
        self.assertIn('<span class="nav-label">Abmelden</span>', logout)

    def test_role_actions_not_exposed_to_regular_users(self):
        self.assertNotIn('class="creator-mode-button"', self.render_shell())
        staff = self.render_shell(superuser=True)
        self.assertEqual(staff.count('class="creator-mode-button"'), 2)
        for label in ("Admin-Test", "Live-Ticker-Test", "Manager", "Creator Mode"):
            self.assertIn(f'class="nav-label">{label}<', staff)

    def test_only_explicit_desktop_state_changes_shell_width(self):
        css = Path("game/static/game/css/navigation-shell.css").read_text()
        desktop = css.split("@media (min-width: 761px) {")[1].split("@media (max-width: 760px)")[0]
        self.assertIn('html[data-nav-state="collapsed"] .dashboard-scaler', desktop)
        self.assertIn("--sidebar: 80px", desktop)
        self.assertIn("--dashboard-content-width: calc(var(--dashboard-shell-width) - var(--sidebar))", desktop)
        self.assertNotIn("data-shell-mode", desktop)
        self.assertNotIn("1177", css)
        self.assertNotIn("--game-scale", css)
        self.assertIn("clip-path: inset(50%)", css)
        self.assertIn(":focus-visible", css)

    def test_toggle_has_a_visible_button_frame_and_double_arrow(self):
        html = self.render_shell()
        toggle = html.split('id="nav-toggle"')[1].split("</button>")[0]
        self.assertIn('aria-label="Navigation einklappen"', toggle)
        self.assertIn('m11 6-6 6 6 6M19 6l-6 6 6 6', toggle)
        css = Path("game/static/game/css/navigation-shell.css").read_text()
        rule = css.split(".nav-shell-toggle {", 1)[1].split("}", 1)[0]
        self.assertIn("border: 1px solid var(--cyan)", rule)
        self.assertIn("z-index: 3", rule)
        self.assertIn("display: inline-flex", rule)
        self.assertIn("justify-content: center", rule)