"""Testy trybu prywatności (rozmycie tła) – Playwright + syntetyczny/stockowy film testowy.
Uruchom:  python3 tests/test_privacy.py http://localhost:8765/index.html [chromium|webkit]
Kamera: --use-file-for-fake-video-capture=$FAKE_VIDEO (domyślnie /workspace/testmedia/squat.y4m – klip stockowy, NIE nagranie klienta).
Film z pliku: $FILE_VIDEO (domyślnie /workspace/testmedia/squat.mp4). Żadne media nie są częścią repozytorium."""
import sys, os, json, subprocess, tempfile, glob
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765/index.html'
ENGINE = sys.argv[2] if len(sys.argv) > 2 else 'chromium'
FAKE = os.environ.get('FAKE_VIDEO', '/workspace/testmedia/squat.y4m')
FILEV = os.environ.get('FILE_VIDEO', '/workspace/testmedia/squat.mp4')
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'screenshots')
ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', f'--use-file-for-fake-video-capture={FAKE}',
        '--no-sandbox', '--autoplay-policy=no-user-gesture-required', '--enable-unsafe-swiftshader']
res = []
def check(name, ok, info=''):
    res.append(bool(ok)); print(('PASS' if ok else 'FAIL'), name, info, flush=True)

# średni gradient (ostrość) regionu [x0,x1]×[y0,y1] (ułamki) – płótno vs. surowa klatka wideo
JS_SHARP = """([x0,x1,y0,y1])=>{
  const c=document.getElementById('view'),v=document.getElementById('video'),w=c.width,h=c.height;
  const t=document.createElement('canvas');t.width=w;t.height=h;t.getContext('2d').drawImage(v,0,0,w,h);
  const mir=__bikerc.mirror;
  const g=(cv)=>{const X0=Math.round(x0*w),X1=Math.round(x1*w),Y0=Math.round(y0*h),Y1=Math.round(y1*h);
    const d=cv.getContext('2d').getImageData(X0,Y0,X1-X0,Y1-Y0);const W=d.width,H=d.height;let s=0,n=0;
    for(let y=0;y<H-1;y++)for(let x=0;x<W-1;x++){const i=(y*W+x)*4,j=i+4,k=i+W*4;
      const a=d.data[i]*.3+d.data[i+1]*.59+d.data[i+2]*.11,b=d.data[j]*.3+d.data[j+1]*.59+d.data[j+2]*.11,e=d.data[k]*.3+d.data[k+1]*.59+d.data[k+2]*.11;
      s+=Math.abs(a-b)+Math.abs(a-e);n++}return s/n};
  // surowa klatka musi być lustrzana tak jak płótno
  let raw=t; if(mir){raw=document.createElement('canvas');raw.width=w;raw.height=h;const q=raw.getContext('2d');q.translate(w,0);q.scale(-1,1);q.drawImage(t,0,0)}
  return {canvas:g(c),raw:g(raw)}}"""
BG = [0.0, 0.10, 0.05, 0.85]     # lewy brzeg kadru: ściana/rama (tło)

def person_box(page):
    return page.evaluate("""()=>{const lm=__bikerc.lastLm;if(!lm)return null;const m=__bikerc.mirror;
      const xs=[11,12,23,24].map(i=>m?1-lm[i].x:lm[i].x),ys=[11,12,23,24].map(i=>lm[i].y);
      return [Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)]}""")

def ratio(page, box):
    r = page.evaluate(JS_SHARP, box); return r['canvas'] / max(r['raw'], 1e-6), r

def start_camera(page):
    page.click('#btn-empty-start')
    page.wait_for_function('window.__bikerc.nPose>10', timeout=120000)
    page.wait_for_timeout(1500)

def run(p):
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=ARGS) if ENGINE == 'chromium' else p.webkit.launch()
    ctx = br.new_context(viewport={'width': 1280, 'height': 900}, permissions=['camera'], accept_downloads=True)
    page = ctx.new_page(); errs = []
    if os.environ.get('NOFILTER'):   # symulacja Safari bez ctx.filter – zapasowe rozmycie przez zmniejszanie
        page.add_init_script("Object.defineProperty(CanvasRenderingContext2D.prototype,'filter',{get(){return 'none'},set(v){}})")
        print('tryb NOFILTER: ctx.filter wyłączone')
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.goto(URL + ('&' if '?' in URL else '?') + 'mp=local', wait_until='load'); page.wait_for_timeout(1200)
    # --- UI i trwałość
    check('domyślnie włączone (przełącznik + przycisk na podglądzie)', page.is_checked('#chk-priv') and page.get_attribute('#s-priv', 'aria-pressed') == 'true')
    page.click('#chk-priv', force=True)
    check('wyłączenie zapisuje się w localStorage', page.evaluate("localStorage.getItem('bikerc.privacy.v1')") == '0' and page.get_attribute('#s-priv', 'aria-pressed') == 'false')
    page.reload(wait_until='load'); page.wait_for_timeout(800)
    check('ustawienie „wyłączone” przetrwało odświeżenie', not page.is_checked('#chk-priv'))
    page.click('#s-priv', force=True)
    page.reload(wait_until='load'); page.wait_for_timeout(800)
    check('ustawienie „włączone” przetrwało odświeżenie', page.is_checked('#chk-priv') and page.evaluate('__bikerc.priv') is True)

    if ENGINE == 'chromium':
        start_camera(page)
        page.uncheck('#chk-skel'); page.uncheck('#chk-labels'); page.wait_for_timeout(500)
        r, raw = ratio(page, BG)
        check('KAMERA: tło rozmyte (gradient ≤ 35% oryginału)', r <= .35, f'{r:.2f} {raw}')
        pb = person_box(page)
        rp, rawp = ratio(page, pb)
        check('KAMERA: sylwetka ostra (gradient ≥ 60% oryginału)', rp >= .6, f'{rp:.2f} {rawp} box={pb}')
        check('KAMERA: maska segmentacji dostarczona', (page.evaluate('__priv.cov') or 0) > .02, str(page.evaluate('__priv.cov')))
        page.locator('#stage').screenshot(path=f'{SHOTS}/privacy-blur-on.png')
        # ostrzeżenie: pomiary nadal działają
        check('KAMERA: kąty nadal liczone', page.evaluate("Object.values(__bikerc.lastVals||{}).some(v=>v!=null)"))
        # --- nagranie → klatki raportu mają rozmyte tło
        page.check('#chk-skel'); page.fill('#in-client', 'Test Prywatności'); page.fill('#in-bike', 'Rower testowy')
        page.click('#btn-rec'); page.wait_for_function('window.__bikerc.rec&&window.__bikerc.rec.frames.length>25', timeout=60000)
        page.wait_for_timeout(2500); page.click('#btn-rec'); page.wait_for_timeout(800)
        caps = page.evaluate("(()=>{const c=__bikerc.last&&__bikerc.last.caps||{};return Object.keys(c).map(k=>({k,priv:c[k].priv,len:c[k].img.length}))})()")
        check('RAPORT: klatki zapisane z flagą prywatności', len(caps) >= 1 and all(c['priv'] for c in caps), json.dumps(caps))
        cg = page.evaluate("""async()=>{const c=__bikerc.last.caps.max||__bikerc.last.caps.min;const im=new Image();im.src=c.img;await im.decode();
          const t=document.createElement('canvas');t.width=im.width;t.height=im.height;const q=t.getContext('2d');q.drawImage(im,0,0);
          const X1=Math.round(.1*t.width),Y0=Math.round(.05*t.height),Y1=Math.round(.85*t.height);const d=q.getImageData(0,Y0,X1,Y1-Y0);const W=d.width,H=d.height;let s=0,n=0;
          for(let y=0;y<H-1;y++)for(let x=0;x<W-1;x++){const i=(y*W+x)*4;s+=Math.abs(d.data[i+1]-d.data[i+5])+Math.abs(d.data[i+1]-d.data[i+W*4+1]);n++}return s/n}""")
        check('RAPORT: obraz w kluczowej klatce ma rozmyte tło', cg < 4.0, f'gradient={cg:.2f}')
        # --- zrzut PNG
        page.locator('#btn-snap').scroll_into_view_if_needed()
        try:
            with page.expect_download(timeout=15000) as dl: page.click('#btn-snap')
            check('ZRZUT: PNG pobrany', dl.value.suggested_filename.endswith('.png'))
            sp = tempfile.mktemp(suffix='.png'); dl.value.save_as(sp)
            from PIL import Image; import numpy as np
            a = np.asarray(Image.open(sp).convert('L')).astype(float); h, w = a.shape
            reg = a[int(.05*h):int(.85*h), :int(.1*w)]; g = (abs(np.diff(reg, axis=0)).mean() + abs(np.diff(reg, axis=1)).mean())
            check('ZRZUT: tło na zrzucie rozmyte', g < 8, f'g={g:.2f}')
        except Exception as e:
            check('ZRZUT: PNG', False, str(e)[:120])
        # --- PDF
        page.locator('#btn-pdf').scroll_into_view_if_needed()
        try:
            with page.expect_download(timeout=120000) as dl: page.click('#btn-pdf')   # desktop: bezpośrednie pobranie
            pp = tempfile.mktemp(suffix='.pdf'); dl.value.save_as(pp)
        except Exception as e:
            pp = None; print('pdf err', str(e)[:150])
        if pp is None:
            check('PDF: wygenerowany', False, 'brak pobrania')
        else:
            check('PDF: wygenerowany', open(pp, 'rb').read(5) == b'%PDF-')
            d = tempfile.mkdtemp(); subprocess.run(['pdfimages', '-j', pp, d + '/im'], check=False)
            from PIL import Image; import numpy as np
            fs = [f for f in sorted(glob.glob(d + '/im*')) if Image.open(f).size[0] > 300]
            vals = []
            for f in fs:
                a = np.asarray(Image.open(f).convert('L')).astype(float); h, w = a.shape
                reg = a[int(.05*h):int(.85*h), :int(.1*w)]; vals.append(abs(np.diff(reg, axis=0)).mean() + abs(np.diff(reg, axis=1)).mean())
            check('PDF: obrazy osadzone w raporcie mają rozmyte tło', len(fs) >= 1 and max(vals) < 8, f'{len(fs)} obr., g={[round(v,2) for v in vals]}')
        # --- wyłączenie → ostre tło
        page.click('#s-priv', force=True); page.wait_for_timeout(1500)
        r2, raw2 = ratio(page, BG)
        check('KAMERA: po wyłączeniu tło ostre (≥ 80%)', r2 >= .8, f'{r2:.2f} {raw2}')
        page.locator('#stage').screenshot(path=f'{SHOTS}/privacy-blur-off.png')
        page.click('#s-priv', force=True); page.wait_for_timeout(1200)
        # --- fail-closed: model nic nie zwraca => cały kadr rozmyty
        page.evaluate("(()=>{const l=__bikerc.landmarker;const o=l.detectForVideo.bind(l);l.__o=o;l.detectForVideo=()=>({landmarks:[],segmentationMasks:[]})})()")
        page.wait_for_timeout(1800)
        rf, rawf = ratio(page, [0.0, 1.0, 0.05, 0.95])
        check('FAIL-CLOSED: brak sylwetki => cały kadr rozmyty', rf <= .35, f'{rf:.2f} {rawf}')
        page.evaluate("(()=>{const l=__bikerc.landmarker;l.detectForVideo=l.__o})()")
        page.click('#btn-cam'); page.wait_for_timeout(500)

    # --- film z pliku (działa też w WebKit)
    if ENGINE == 'chromium' and os.path.exists(FILEV):   # headless WebKit w tym środowisku wywala się na inferencji (też bez zmian prywatności)
        page.set_input_files('#file-video', FILEV)
        page.wait_for_function('window.__bikerc.running&&window.__bikerc.nPose>5', timeout=120000)
        page.uncheck('#chk-skel'); page.uncheck('#chk-labels')
        page.wait_for_timeout(1500)
        r, raw = ratio(page, BG)
        check(f'FILM [{ENGINE}]: tło rozmyte', r <= .4, f'{r:.2f} {raw}')
        pb = person_box(page); rp, rawp = ratio(page, pb) if pb else (0, {})
        check(f'FILM [{ENGINE}]: sylwetka ostra', rp >= .55, f'{rp:.2f} {rawp}')
        page.locator('#stage').screenshot(path='/tmp/privacy-film-tmp.png')
        page.click('#v-play'); page.wait_for_timeout(600)
        page.click('#s-priv', force=True); page.wait_for_timeout(1200)
        r3, raw3 = ratio(page, BG)
        check(f'FILM [{ENGINE}]: przełączenie na wstrzymanym filmie przerysowuje obraz (ostre)', r3 >= .75, f'{r3:.2f} {raw3}')
        page.click('#s-priv', force=True); page.wait_for_timeout(1200)
        r4, raw4 = ratio(page, BG)
        check(f'FILM [{ENGINE}]: ponowne włączenie na wstrzymanym filmie rozmywa', r4 <= .4, f'{r4:.2f} {raw4}')
    if ENGINE != 'chromium': print('UWAGA: WebKit – sprawdzono tylko UI/trwałość (inferencja MediaPipe niedostępna w headless WebKit na tym hoście)')
    check('brak błędów JS', not errs, '; '.join(errs)[:300])
    ctx.close(); br.close()

with sync_playwright() as p:
    run(p)
print(f'\n{sum(res)}/{len(res)} OK')
sys.exit(0 if all(res) else 1)
