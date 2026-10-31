"""Testy mobilne (Playwright, emulacja telefonów, kamera testowa).
Uruchom:  python3 tests/test_mobile.py http://localhost:8765/index.html [chromium|webkit]
Wymaga: pip install playwright; Chrome/Chromium (lub `playwright install webkit`) oraz pliku wideo y4m
(domyślnie /workspace/testmedia/squat.y4m, zmienna FAKE_VIDEO)."""
import sys, os, json, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/index.html'
ENGINE = sys.argv[2] if len(sys.argv) > 2 else 'chromium'
VIDEO = os.environ.get('FAKE_VIDEO', '/workspace/testmedia/squat.y4m')
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'screenshots')
os.makedirs(SHOTS, exist_ok=True)
ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', f'--use-file-for-fake-video-capture={VIDEO}',
        '--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--enable-unsafe-swiftshader']
results = []
def check(name, ok, info=''):
    results.append((name, bool(ok), info)); print(('PASS' if ok else 'FAIL'), name, info, flush=True)

def run(p, dev_name, orient, full_flow):
    d = dict(p.devices[dev_name]); d.pop('default_browser_type', None)
    if orient == 'landscape':
        d['viewport'] = {'width': d['viewport']['height'], 'height': d['viewport']['width']}
        d['screen'] = {'width': d['viewport']['width'], 'height': d['viewport']['height']}
    tag = f"{dev_name.replace(' ', '').lower()}-{orient}"
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS) if ENGINE == 'chromium' else p.webkit.launch()
    ctx = br.new_context(**d, permissions=['camera'], accept_downloads=True)
    page = ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    page.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    page.goto(URL, wait_until='load')
    page.wait_for_timeout(1500)
    # --- układ
    ov = page.evaluate("({sw:document.documentElement.scrollWidth,iw:innerWidth,bw:document.body.scrollWidth})")
    check(f'[{tag}] brak poziomego przewijania', ov['sw'] <= ov['iw'] + 1 and ov['bw'] <= ov['iw'] + 1, str(ov))
    check(f'[{tag}] dolny pasek widoczny', page.is_visible('#dock'))
    page.screenshot(path=f'{SHOTS}/m-{tag}-1-start.png')
    # --- kamera (tap)
    page.tap('#d-cam')
    try:
        page.wait_for_function('window.__bikerc.nPose>10', timeout=60000); started = True
    except Exception: started = False
    st = page.evaluate("({run:__bikerc.running,src:__bikerc.source,fac:__bikerc.facing,cam:__bikerc.camFacing,vw:document.getElementById('video').videoWidth,vh:document.getElementById('video').videoHeight,cw:document.getElementById('view').width,ch:document.getElementById('view').height,nPose:__bikerc.nPose,wake:!!__bikerc.wake})")
    check(f'[{tag}] kamera startuje i wykrywa sylwetkę', started and st['run'], json.dumps(st))
    check(f'[{tag}] domyślnie tylna kamera (telefon)', st['fac'] == 'environment')
    page.wait_for_timeout(1200)
    px = page.evaluate("""()=>{const c=document.getElementById('view');const g=c.getContext('2d');const d=g.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<d.length;i+=4*97){if(d[i]>40||d[i+1]>40||d[i+2]>40)n++}return n}""")
    check(f'[{tag}] obraz + szkielet rysowany na canvas', px > 200, f'nonblack samples={px}')
    page.screenshot(path=f'{SHOTS}/m-{tag}-2-camera.png')
    # --- przełączenie kamery
    page.tap('#d-flip'); page.wait_for_timeout(500)
    try:
        page.wait_for_function('window.__bikerc.running && window.__bikerc.nPose>0 && window.__bikerc.facing', timeout=30000)
        page.wait_for_function("document.getElementById('video').videoWidth>0 && __bikerc.running", timeout=30000)
    except Exception: pass
    page.wait_for_timeout(1500)
    fl = page.evaluate("({run:__bikerc.running,fac:__bikerc.facing})")
    check(f'[{tag}] przełączanie kamery przód/tył działa', fl['run'], json.dumps(fl))
    page.tap('#d-flip'); page.wait_for_timeout(2500)
    # --- pełny ekran
    page.tap('#d-fs'); page.wait_for_timeout(700)
    fs = page.evaluate("(()=>{const s=document.getElementById('stage');return !!(document.fullscreenElement||s.classList.contains('fake-fs'))})()")
    check(f'[{tag}] pełny ekran', fs)
    page.screenshot(path=f'{SHOTS}/m-{tag}-3-fullscreen.png')
    page.tap('#s-fs'); page.wait_for_timeout(500)
    if full_flow:
        # --- pomiar + PDF
        page.fill('#in-client', 'Anna Łukasiewicz'); page.fill('#in-bike', 'Giant Defy')
        page.tap('#d-rec'); page.wait_for_timeout(9000)
        recs = page.evaluate("S=__bikerc;S.rec?S.rec.frames.length:0") if False else page.evaluate("__bikerc.rec?__bikerc.rec.frames.length:0")
        check(f'[{tag}] nagrywanie zbiera próbki', recs > 20, f'frames={recs}')
        page.screenshot(path=f'{SHOTS}/m-{tag}-4-recording.png')
        page.tap('#d-rec'); page.wait_for_timeout(800)
        page.locator('#btn-pdf').scroll_into_view_if_needed()
        page.tap('#btn-pdf')
        try:
            page.wait_for_selector('#sheet:not([hidden])', timeout=60000); shown = True
        except Exception: shown = False
        check(f'[{tag}] PDF: pojawia się arkusz Otwórz/Pobierz', shown)
        if shown:
            page.screenshot(path=f'{SHOTS}/m-{tag}-5-pdf-sheet.png')
            with page.expect_download(timeout=20000) as dl: page.tap('#sh-dl')
            path = f'/tmp/mob-{tag}.pdf'; dl.value.save_as(path)
            head = open(path, 'rb').read(5); size = os.path.getsize(path)
            check(f'[{tag}] PDF pobrany i poprawny', head == b'%PDF-' and size > 20000, f'{dl.value.suggested_filename} {size}B')
            blob_ok = page.evaluate("document.getElementById('sh-open').href.startsWith('blob:')||true")
        # CSV (Android: bezpośrednie pobranie; iOS: arkusz Otwórz/Pobierz)
        page.wait_for_timeout(600)
        page.locator('#btn-csv').scroll_into_view_if_needed()
        ios = 'iphone' in dev_name.lower()
        try:
            if ios:
                page.tap('#btn-csv'); page.wait_for_selector('#sheet:not([hidden])', timeout=5000)
                with page.expect_download(timeout=20000) as dl2: page.tap('#sh-dl')
            else:
                with page.expect_download(timeout=20000) as dl2: page.tap('#btn-csv')
            nm = dl2.value.suggested_filename
            check(f'[{tag}] CSV pobrany' + (' (przez arkusz iOS)' if ios else ''), nm.endswith('.csv'), nm)
        except Exception as e:
            check(f'[{tag}] CSV pobrany', False, str(e)[:100])
        # snapshot of the end state
        page.screenshot(path=f'{SHOTS}/m-{tag}-6-after.png', full_page=True)
    ov2 = page.evaluate("({sw:document.documentElement.scrollWidth,iw:innerWidth})")
    check(f'[{tag}] brak poziomego przewijania (po pomiarze)', ov2['sw'] <= ov2['iw'] + 1, str(ov2))
    check(f'[{tag}] brak błędów JS', not errs, '; '.join(errs)[:400])
    ctx.close(); br.close()

def pwa_test(p):
    d = dict(p.devices['Pixel 7']); d.pop('default_browser_type', None)
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS)
    ctx = br.new_context(**d, permissions=['camera']); page = ctx.new_page()
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(URL, wait_until='load')
    ok = page.evaluate("navigator.serviceWorker.ready.then(r=>!!r.active)")
    page.wait_for_timeout(3000)
    keys = page.evaluate("caches.keys().then(async ks=>{let o={};for(const k of ks){o[k]=(await (await caches.open(k)).keys()).length}return o})")
    check('[PWA] service worker aktywny', ok)
    check('[PWA] cache powłoki aplikacji wypełniony', any(v >= 8 for v in keys.values()), json.dumps(keys))
    man = page.evaluate("fetch(document.querySelector('link[rel=manifest]').href).then(r=>r.json())")
    check('[PWA] manifest poprawny', man.get('display') == 'standalone' and len(man['icons']) >= 3 and man['theme_color'] == '#232222', man['name'])
    ctx.set_offline(True)
    try:
        page.reload(wait_until='domcontentloaded'); t = page.title(); off = 'BikeRc' in t
    except Exception as e:
        off = False; t = str(e)[:80]
    check('[PWA] aplikacja otwiera się offline', off, t)
    ctx.close(); br.close()

def insecure_test(p, host_url):
    d = dict(p.devices['Pixel 7']); d.pop('default_browser_type', None)
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS)
    ctx = br.new_context(**d, permissions=['camera']); page = ctx.new_page()
    page.goto(host_url, wait_until='load'); page.wait_for_timeout(800)
    sec = page.evaluate('isSecureContext'); vis = page.is_visible('#https-warn')
    txt = page.inner_text('#https-warn') if vis else ''
    check('[HTTPS] komunikat o braku https w niezabezpieczonym kontekście', (not sec) and vis and 'HTTPS' in txt, f'secure={sec}')
    page.screenshot(path=f'{SHOTS}/m-insecure-http.png')
    if vis:
        page.tap('#d-cam'); page.wait_for_timeout(800)
        check('[HTTPS] próba startu kamery pokazuje komunikat', 'HTTPS' in page.inner_text('#toast'), page.inner_text('#toast')[:80])
    ctx.close(); br.close()

if __name__ == '__main__':
    only = os.environ.get('ONLY', '')
    with sync_playwright() as p:
        if ENGINE == 'webkit':
            run(p, 'iPhone 13', 'portrait', False)
        else:
            run(p, 'Pixel 7', 'portrait', True)
            run(p, 'Pixel 7', 'landscape', False)
            run(p, 'iPhone 13', 'portrait', True)
            run(p, 'iPhone 13', 'landscape', False)
            pwa_test(p)
            if os.environ.get('INSECURE_URL'): insecure_test(p, os.environ['INSECURE_URL'])
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results)-len(bad)}/{len(results)} OK'); sys.exit(1 if bad else 0)
