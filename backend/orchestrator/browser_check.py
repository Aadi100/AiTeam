"""
Browser check: open the finished site in a real (headless) browser and report what is broken.

check(url, shot_path) -> (ok, report_text, data)

It looks for what a person would notice on first open: the page failing to load, JavaScript errors, 404s for scripts,
styles or images, broken internal links, a blank page, buttons that throw when clicked, and horizontal overflow on a
phone-sized screen. It also saves a screenshot for the user. It cannot judge visual taste (DeepSeek has no vision),
so the report is structural; the screenshot is for you to look at.

Needs the `playwright` package and an installed Edge or Chrome (override with ADION_BROWSER=msedge|chrome|chromium).
If neither is available the check is skipped, never failed.
"""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

MAX_LINKS = 8
MAX_CLICKS = 6


class BrowserUnavailable(Exception):
    pass


def _launch(p):
    order = [os.getenv('ADION_BROWSER')] if os.getenv('ADION_BROWSER') else ['msedge', 'chrome', None]
    last = ''
    for ch in order:
        try:
            return p.chromium.launch(channel=ch, headless=True) if ch else p.chromium.launch(headless=True)
        except Exception as e:  # noqa: BLE001
            last = str(e).splitlines()[0][:160]
    raise BrowserUnavailable(f'no Edge/Chrome found ({last})')


def _short(url, origin):
    return url[len(origin):] or '/' if url.startswith(origin) else url


def check(url, shot_path=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return True, 'Browser check skipped: the playwright package is not installed.', {'skipped': True}
    origin = '{0.scheme}://{0.netloc}'.format(urlparse(url))
    issues, data = [], {'url': url, 'links': [], 'buttons': 0, 'forms': 0, 'title': '', 'textLength': 0,
                        'at': datetime.utcnow().isoformat() + 'Z', 'screenshot': False}

    def add(level, msg):
        if not any(i['msg'] == msg for i in issues):
            issues.append({'level': level, 'msg': msg[:300]})

    try:
        with sync_playwright() as p:
            browser = _launch(p)
            try:
                ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
                page = ctx.new_page()
                page.set_default_timeout(8000)
                console, js = [], []
                page.on('console', lambda m: console.append(m.text) if m.type == 'error' else None)
                page.on('pageerror', lambda e: js.append(str(e)[:300]))
                page.on('dialog', lambda d: d.dismiss())
                responded = set()

                def on_response(r):
                    responded.add(r.url)
                    if r.status >= 400 and 'favicon' not in r.url:
                        add('error' if r.url.startswith(origin) else 'warn', f'HTTP {r.status} for {_short(r.url, origin)}')

                def on_failed(r):
                    if 'favicon' not in r.url and r.url not in responded:
                        add('error' if r.url.startswith(origin) else 'warn', f'request failed: {_short(r.url, origin)}')
                page.on('response', on_response)
                page.on('requestfailed', on_failed)

                resp = page.goto(url, wait_until='load')
                try:
                    page.wait_for_load_state('networkidle', timeout=4000)
                except Exception:  # noqa: BLE001 - long-polling pages never go idle
                    pass
                if resp is None or resp.status >= 400:
                    add('error', f'the main page returned HTTP {resp.status if resp else "no response"}')
                data['title'] = page.title()
                data['textLength'] = page.evaluate('document.body ? document.body.innerText.trim().length : 0')
                visual = page.evaluate("document.querySelectorAll('img,canvas,svg,video').length")
                if data['textLength'] < 15 and not visual:
                    add('error', 'the page renders blank (no visible text or images)')
                for m in js:
                    add('error', f'JavaScript error on load: {m}')
                for m in console:
                    if not m.startswith('Failed to load resource'):   # already reported with its URL above
                        add('error', f'console error: {m[:200]}')
                broken = page.evaluate("[...document.images].filter(i => i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'))")
                for src in broken[:5]:
                    add('error', f'image does not load: {src}')
                if shot_path:
                    os.makedirs(os.path.dirname(os.path.abspath(shot_path)), exist_ok=True)
                    page.screenshot(path=shot_path, full_page=True)
                    data['screenshot'] = True

                # internal links
                hrefs = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href)")
                seen = []
                for h in hrefs:
                    h = h.split('#')[0]
                    if h.startswith(origin) and h != url and h not in seen and not h.endswith(('.zip', '.pdf')):
                        seen.append(h)
                for h in seen[:MAX_LINKS]:
                    try:
                        st = ctx.request.get(h, timeout=6000).status
                    except Exception:  # noqa: BLE001
                        st = 0
                    data['links'].append({'url': _short(h, origin), 'status': st})
                    if st >= 400 or st == 0:
                        add('error', f'internal link is broken: {_short(h, origin)} (HTTP {st or "no response"})')

                # click the buttons; anything that throws is a real bug
                btns = page.locator('button:visible, [role=button]:visible, input[type=button]:visible')
                n = btns.count()
                data['buttons'] = n
                data['forms'] = page.locator('form').count()
                for i in range(min(n, MAX_CLICKS)):
                    before = len(js)
                    try:
                        label = (btns.nth(i).inner_text() or btns.nth(i).get_attribute('value') or f'#{i + 1}').strip()[:30]
                        btns.nth(i).click(timeout=2000)
                        page.wait_for_timeout(200)
                    except Exception:  # noqa: BLE001 - not clickable / detached: not the site's fault
                        continue
                    for m in js[before:]:
                        add('error', f'clicking "{label}" raised: {m}')
                    if page.url.split('#')[0] != url.split('#')[0]:
                        page.goto(url, wait_until='load')
                        btns = page.locator('button:visible, [role=button]:visible, input[type=button]:visible')

                # phone layout
                mobile = browser.new_context(viewport={'width': 390, 'height': 800}).new_page()
                mobile.goto(url, wait_until='load')
                if mobile.evaluate('document.documentElement.scrollWidth > window.innerWidth + 8'):
                    add('warn', 'the page scrolls sideways on a phone-sized screen (390px wide)')
            finally:
                browser.close()
    except BrowserUnavailable as e:
        return True, f'Browser check skipped: {e}', {'skipped': True, 'reason': str(e)}
    except Exception as e:  # noqa: BLE001
        add('error', f'the browser check itself failed: {type(e).__name__}: {str(e)[:200]}')

    errors = [i for i in issues if i['level'] == 'error']
    warns = [i for i in issues if i['level'] == 'warn']
    data['issues'] = issues[:20]
    data['ok'] = not errors
    lines = [f'BROWSER CHECK of {_short(url, origin)} (title: "{data["title"]}", {data["textLength"]} chars of text, '
             f'{data["buttons"]} buttons, {len(data["links"])} internal links tried)']
    if errors:
        lines.append('ERRORS:\n' + '\n'.join(f'- {i["msg"]}' for i in errors))
    if warns:
        lines.append('WARNINGS:\n' + '\n'.join(f'- {i["msg"]}' for i in warns))
    if not issues:
        lines.append('No problems found: it loads, no script errors, links and buttons work.')
    return (not errors), '\n'.join(lines), data
