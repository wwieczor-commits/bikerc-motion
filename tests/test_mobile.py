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
    page.tap('#s-flip'); page.wait_for_timeout(500)
    try:
        page.wait_for_function('window.__bikerc.running && window.__bikerc.nPose>0 && window.__bikerc.facing', timeout=30000)
        page.wait_for_function("document.getElementById('video').videoWidth>0 && __bikerc.running", timeout=30000)
    except Exception: pass
    page.wait_for_timeout(1500)
    fl = page.evaluate("({run:__bikerc.running,fac:__bikerc.facing})")
    check(f'[{tag}] przełączanie kamery przód/tył działa', fl['run'], json.dumps(fl))
    page.tap('#s-flip'); page.wait_for_timeout(2500)
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

FILE_VIDEO = os.environ.get('TEST_FILE_VIDEO', '/workspace/testmedia/squat.mp4')   # mp4 H.264
BROKEN_VIDEO = os.environ.get('TEST_BROKEN_VIDEO', '/workspace/testmedia/broken.mov')

def video_file_test(p, dev_name, vp=None):
    """Wczytanie filmu z telefonu: przyciski, odtwarzacz, pomiar na filmie, PDF, błąd formatu, brak przepełnienia."""
    d = dict(p.devices[dev_name]); d.pop('default_browser_type', None)
    if vp: d['viewport'] = vp; d['screen'] = vp
    tag = f"video-{dev_name.replace(' ', '').lower()}" + (f"-{vp['width']}" if vp else '')
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS)   # kamera NIE jest używana
    ctx = br.new_context(**d, accept_downloads=True); page = ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    page.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    page.goto(URL, wait_until='load'); page.wait_for_timeout(1200)
    iw = page.evaluate('innerWidth')
    check(f'[{tag}] brak linku „System pomiarów” / bikerc-5a1dd.web.app', 'System pomiarów' not in page.content() and 'bikerc-5a1dd' not in page.content())
    # --- przyciski widoczne
    check(f'[{tag}] przycisk „Film” w dolnym pasku widoczny', page.is_visible('#d-film'))
    check(f'[{tag}] „Wczytaj film z telefonu” na ekranie startowym', page.is_visible('#btn-empty-film'))
    inp = page.evaluate("({acc:file_video.accept,cap:file_video.hasAttribute('capture'),capRec:file_rec.getAttribute('capture')})") if False else \
        page.evaluate("({acc:document.getElementById('file-video').accept,cap:document.getElementById('file-video').hasAttribute('capture'),capRec:document.getElementById('file-rec').getAttribute('capture')})")
    check(f'[{tag}] input video/* bez atrybutu capture (galeria/pliki)', inp['acc'] == 'video/*' and not inp['cap'], json.dumps(inp))
    check(f'[{tag}] drugi input z capture (nagraj nowy film)', inp['capRec'] == 'environment')
    boxes = page.evaluate("[...document.querySelectorAll('#dock .btn')].map(b=>{const r=b.getBoundingClientRect();return [Math.round(r.left),Math.round(r.right),Math.round(r.width),b.scrollWidth>b.clientWidth+1]})")
    fit = all(b[0] >= 0 and b[1] <= iw for b in boxes) and not any(b[3] for b in boxes) and all(boxes[i][1] <= boxes[i+1][0] for i in range(len(boxes)-1))
    check(f'[{tag}] dolny pasek mieści się w {iw}px (bez nakładania i ucinania)', fit, str(boxes))
    page.screenshot(path=f'{SHOTS}/m-{tag}-1-start.png')
    # --- prawdziwa ścieżka: tap w „Film” otwiera wybór pliku
    with page.expect_file_chooser(timeout=5000) as fc: page.tap('#d-film')
    check(f'[{tag}] tap „Film” otwiera systemowy wybór pliku', fc.value is not None)
    with page.expect_file_chooser(timeout=5000) as fc2: page.tap('#btn-empty-film')
    fc2.value.set_files(FILE_VIDEO)
    try:
        page.wait_for_function('window.__bikerc.nPose>10', timeout=60000); ok = True
    except Exception: ok = False
    st = page.evaluate("({run:__bikerc.running,src:__bikerc.source,vw:video.videoWidth,paused:video.paused,mir:__bikerc.mirror,vis:!document.getElementById('vctl').hidden,n:__bikerc.nPose})")
    check(f'[{tag}] film wczytany, szkielet wykrywany', ok and st['run'] and st['src'] == 'file' and st['vw'] > 0, json.dumps(st))
    check(f'[{tag}] panel odtwarzania widoczny, bez lustra', st['vis'] and not st['mir'])
    page.wait_for_timeout(800)
    px = page.evaluate("""()=>{const c=document.getElementById('view');const g=c.getContext('2d');const d=g.getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<d.length;i+=4*97){if(d[i]>40||d[i+1]>40||d[i+2]>40)n++}return n}""")
    check(f'[{tag}] klatka filmu + szkielet na canvas', px > 200, f'samples={px}')
    page.screenshot(path=f'{SHOTS}/m-{tag}-2-playing.png')
    # --- kontrolki
    page.locator('#vctl').scroll_into_view_if_needed()
    page.tap('#seg-speed button[data-r="0.5"]'); page.wait_for_timeout(200)
    check(f'[{tag}] prędkość 0,5×', page.evaluate('video.playbackRate') == 0.5)
    page.tap('#seg-speed button[data-r="0.25"]'); page.wait_for_timeout(200)
    check(f'[{tag}] prędkość 0,25×', page.evaluate('video.playbackRate') == 0.25)
    page.tap('#v-play'); page.wait_for_timeout(400)
    check(f'[{tag}] pauza działa', page.evaluate('video.paused') and page.inner_text('#v-play').strip() == '▶')
    t0 = page.evaluate('video.currentTime'); page.tap('#v-fwd'); page.wait_for_timeout(500); t1 = page.evaluate('video.currentTime')
    check(f'[{tag}] krok o klatkę do przodu', 0.02 < t1 - t0 < 0.06, f'{t0:.3f}->{t1:.3f}')
    page.tap('#v-back'); page.wait_for_timeout(500); t2 = page.evaluate('video.currentTime')
    check(f'[{tag}] krok o klatkę wstecz', abs(t2 - t0) < 0.01, f'{t2:.3f}')
    n0 = page.evaluate('__bikerc.nPose'); page.tap('#v-fwd'); page.wait_for_timeout(700); n1 = page.evaluate('__bikerc.nPose')
    check(f'[{tag}] po kroku klatka jest analizowana', n1 > n0, f'{n0}->{n1}')
    page.evaluate("(()=>{const r=document.getElementById('v-seek');r.value=600;r.dispatchEvent(new Event('input',{bubbles:true}));r.dispatchEvent(new Event('change',{bubbles:true}))})()")
    page.wait_for_timeout(600); dd = page.evaluate('[video.currentTime,video.duration]')
    check(f'[{tag}] suwak przewijania', abs(dd[0] / dd[1] - 0.6) < 0.05, str(dd))
    page.screenshot(path=f'{SHOTS}/m-{tag}-3-paused-controls.png')
    page.tap('#seg-speed button[data-r="1"]'); page.tap('#v-play'); page.wait_for_timeout(600)
    check(f'[{tag}] wznowienie odtwarzania 1×', (not page.evaluate('video.paused')) and page.evaluate('video.playbackRate') == 1)
    # --- pomiar na filmie (0,5× -> czas filmu, nie zegara ściennego)
    page.tap('#seg-speed button[data-r="0.5"]')
    page.fill('#in-client', 'Anna Łukasiewicz'); page.fill('#in-bike', 'Giant Defy')
    page.evaluate("video.currentTime=0"); page.wait_for_timeout(300)
    page.tap('#d-rec'); page.wait_for_timeout(5000)
    live = page.evaluate("({n:__bikerc.rec?__bikerc.rec.frames.length:0,t:__bikerc.rec?__bikerc.rec.frames.at(-1).t:0})")
    page.screenshot(path=f'{SHOTS}/m-{tag}-4-recording.png')
    page.tap('#d-rec'); page.wait_for_timeout(600)
    r = page.evaluate("({n:__bikerc.last.frames.length,dur:__bikerc.last.dur,src:__bikerc.last.source,mono:__bikerc.last.frames.every((f,i,a)=>i==0||f.t>=a[i-1].t),tmax:__bikerc.last.frames.at(-1).t,wall:(__bikerc.last.endedAt-__bikerc.last.startedAt)/1000})")
    check(f'[{tag}] pomiar na filmie zbiera próbki', live['n'] > 5 and r['n'] > 5 and r['src'] == 'file', json.dumps(r))
    check(f'[{tag}] znaczniki czasu = czas filmu (0,5×: czas filmu ≈ ½ czasu zegara)', 0.35 < r['dur'] / r['wall'] < 0.65 and r['tmax'] <= r['dur'] + .05 and r['mono'], json.dumps(r))
    page.locator('#btn-pdf').scroll_into_view_if_needed(); page.tap('#btn-pdf')
    try: page.wait_for_selector('#sheet:not([hidden])', timeout=60000); shown = True
    except Exception: shown = False
    check(f'[{tag}] PDF z pomiaru z filmu: arkusz Otwórz/Pobierz', shown)
    if shown:
        with page.expect_download(timeout=20000) as dl: page.tap('#sh-dl')
        path = f'/tmp/vid-{tag}.pdf'; dl.value.save_as(path)
        check(f'[{tag}] PDF poprawny', open(path, 'rb').read(5) == b'%PDF-' and os.path.getsize(path) > 20000, f'{os.path.getsize(path)}B')
        if tag.endswith('pixel7'): os.system(f'cp {path} /tmp/video-report-sample.pdf')
    # --- koniec filmu przerywa pomiar
    page.evaluate("video.playbackRate=4"); page.wait_for_timeout(200)
    page.evaluate("__bikerc.rec||document.getElementById('btn-rec').click()"); page.wait_for_timeout(300)
    page.evaluate("video.currentTime=Math.max(0,video.duration-1.2)"); page.wait_for_timeout(1500)
    check(f'[{tag}] koniec filmu automatycznie kończy pomiar', page.evaluate('!__bikerc.rec'))
    # --- zły format (.mov/HEVC nieobsługiwany)
    page.tap('#d-cam'); page.wait_for_timeout(400)   # stop
    with page.expect_file_chooser(timeout=5000) as fc3: page.tap('#d-film')
    fc3.value.set_files(BROKEN_VIDEO); page.wait_for_timeout(2500)
    tt = page.inner_text('#toast'); bad = page.evaluate('__bikerc.running')
    check(f'[{tag}] nieobsługiwany format: polski komunikat, brak zawieszenia', ('MP4' in tt) and not bad, tt[:90])
    page.screenshot(path=f'{SHOTS}/m-{tag}-5-format-error.png')
    ov = page.evaluate("({sw:document.documentElement.scrollWidth,iw:innerWidth})")
    check(f'[{tag}] brak poziomego przewijania', ov['sw'] <= ov['iw'] + 1, str(ov))
    check(f'[{tag}] brak błędów JS', not errs, '; '.join(errs)[:400])
    ctx.close(); br.close()

def sw_update_test(p):
    """sw.js v4: network-first dla index.html -> po zmianie na serwerze od razu widać nową wersję."""
    d = dict(p.devices['Pixel 7']); d.pop('default_browser_type', None)
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS)
    ctx = br.new_context(**d); page = ctx.new_page()
    page.goto(URL, wait_until='load'); page.evaluate("navigator.serviceWorker.ready.then(()=>1)"); page.wait_for_timeout(2500)
    v = page.evaluate("fetch('./sw.js').then(r=>r.text()).then(t=>/VERSION = '(v\\d+)'/.exec(t)[1])")
    check('[SW] wersja cache v4+', int(v[1:]) >= 4, v)
    page.reload(wait_until='load')
    served = page.evaluate("fetch('./index.html',{cache:'no-store'}).then(r=>r.text()).then(t=>t.includes('id=\"d-film\"'))")
    check('[SW] index.html zawiera przycisk Film', served)
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
            video_file_test(p, 'Pixel 7'); video_file_test(p, 'iPhone 13'); video_file_test(p, 'Pixel 7', {'width': 360, 'height': 740})
            sw_update_test(p)
            if os.environ.get('INSECURE_URL'): insecure_test(p, os.environ['INSECURE_URL'])
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results)-len(bad)}/{len(results)} OK'); sys.exit(1 if bad else 0)
