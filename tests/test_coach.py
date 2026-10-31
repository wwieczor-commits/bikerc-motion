"""Test trenera głosowego (Playwright, emulacja telefonu, speechSynthesis podmieniony na szpiega).
Uruchom:  python3 tests/test_coach.py http://localhost:8765/index.html
Wymaga: Chrome (/usr/bin/google-chrome), film /workspace/testmedia/squat.mp4 (FILE_VIDEO) i squat.y4m (kamera testowa)."""
import sys, os, json
from playwright.sync_api import sync_playwright
sys.argv = [sys.argv[0]] + sys.argv[1:2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_mobile as t

MOCK = """
(()=>{ window.__spoken=[]; window.SpeechSynthesisUtterance=class{constructor(t){this.text=t;this.volume=1;this.rate=1;this.pitch=1;this.lang='';this.voice=null;this.onend=null;this.onerror=null}};
  const fake={speaking:false,pending:false,paused:false,_u:null,
    getVoices(){return [{name:'Zosia (pl-PL)',lang:'pl-PL',voiceURI:'pl-zosia',default:false,localService:true},{name:'Samantha',lang:'en-US',voiceURI:'en-sam',default:true,localService:true}]},
    speak(u){ window.__spoken.push({t:u.text,vol:u.volume,rate:u.rate,lang:u.lang,voice:u.voice&&u.voice.name,at:Date.now()}); this.speaking=true; this._u=u;
      setTimeout(()=>{this.speaking=false; u.onend&&u.onend({})}, Math.min(600, 40+u.text.length*6)) },
    cancel(){ this.speaking=false; this._u=null }, pause(){}, resume(){}, addEventListener(){}, removeEventListener(){}, onvoiceschanged:null};
  Object.defineProperty(window,'speechSynthesis',{value:fake,configurable:true});
})();
"""
res = []
def check(n, ok, info=''):
    res.append(bool(ok)); print(('PASS' if ok else 'FAIL'), n, info, flush=True)
def spoken(pg): return [s['t'] for s in pg.evaluate('window.__spoken') if s['t'].strip()]

with sync_playwright() as p:
    d = dict(p.devices['Pixel 7']); d.pop('default_browser_type', None)
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=t.ARGS)
    ctx = br.new_context(**d, permissions=['camera'], accept_downloads=True); pg = ctx.new_page()
    pg.add_init_script(MOCK)
    errs = []
    pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
    pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    pg.goto(t.URL, wait_until='load'); pg.wait_for_timeout(1000)
    check('Coach załadowany', pg.evaluate('typeof Coach==="object"&&Coach.supported'))
    check('przycisk wyciszenia w pasku dolnym i na podglądzie', pg.is_visible('#d-voice') and pg.is_visible('#s-voice'))
    iw = pg.evaluate('innerWidth')
    boxes = pg.evaluate("[...document.querySelectorAll('#dock .btn')].map(b=>{const r=b.getBoundingClientRect();return [r.left,r.right]})")
    check('dolny pasek (5 przycisków) mieści się', all(b[0] >= 0 and b[1] <= iw for b in boxes) and all(boxes[i][1] <= boxes[i+1][0]+0.5 for i in range(len(boxes)-1)), str(boxes))
    # ustawienia
    pg.tap('#s-voicecfg'); pg.wait_for_selector('#coach-panel', state='visible')
    check('panel ustawień otwarty, jest lista głosów z polskim', 'pl-PL' in pg.inner_text('#coach-voice'), pg.inner_text('#coach-voice')[:80])
    pg.fill('#coach-vol', '0.6'); pg.dispatch_event('#coach-vol', 'input')
    pg.fill('#coach-rate', '1.2'); pg.dispatch_event('#coach-rate', 'input')
    pg.tap('#coach-level button[data-l="chatty"]') if pg.query_selector('#coach-level button[data-l="chatty"]') else None
    pg.tap('#coach-test'); pg.wait_for_timeout(900)
    sp = pg.evaluate('window.__spoken'); tst = [s for s in sp if 'Test' in s['t'] or 'trener' in s['t']]
    check('Test głosu mówi (pl-PL, głośność/tempo z ustawień)', tst and tst[-1]['lang'].startswith('pl') and abs(tst[-1]['vol']-.6)<.01 and abs(tst[-1]['rate']-1.2)<.01, json.dumps(tst[-1:]))
    cfg = pg.evaluate('JSON.parse(localStorage.getItem("bikerc.coach.v1"))')
    check('ustawienia zapisane w localStorage', cfg and abs(cfg['vol']-.6)<.01 and abs(cfg['rate']-1.2)<.01, json.dumps(cfg))
    pg.tap('#coach-close'); pg.reload(wait_until='load'); pg.wait_for_timeout(800)
    check('ustawienia po przeładowaniu', pg.evaluate('Coach.cfg.vol')==.6 and pg.evaluate('Coach.cfg.level')=='chatty', pg.evaluate('JSON.stringify(Coach.cfg)'))
    # poziom: ustaw "normalny" przez API (UI sprawdzone wyżej)
    pg.evaluate('Coach.set({level:"normal",vol:1,rate:1})')
    # wyciszenie
    pg.tap('#d-voice'); pg.wait_for_timeout(200)
    check('wyciszenie: on=false', pg.evaluate('Coach.cfg.on')==False)
    n0 = len(spoken(pg)); pg.evaluate('Coach.say("to nie powinno zabrzmieć",{p:2})'); pg.wait_for_timeout(500)
    check('po wyciszeniu nic nie jest mówione', len(spoken(pg))==n0)
    pg.tap('#d-voice'); pg.wait_for_timeout(700)
    check('włączenie głosu potwierdzone głosem', any('włączony' in s for s in spoken(pg)), str(spoken(pg)[-2:]))
    # ---- film: pomiar na pliku
    pg.evaluate('window.__spoken.length=0')
    with pg.expect_file_chooser() as fc: pg.tap('#d-film')
    fc.value.set_files(os.environ.get('LONG_VIDEO','/workspace/testmedia/squat_long.mp4')); pg.wait_for_function('__bikerc.nPose>10', timeout=60000)
    pg.wait_for_timeout(1500)
    s1 = spoken(pg); check('film: komunikat startowy + wykrycie sylwetki', any('Film wczytany' in s for s in s1) and any('Widzę sylwetkę' in s for s in s1), str(s1))
    pg.tap('#d-rec'); pg.wait_for_timeout(500)
    check('film: pomiar startuje od razu (bez odliczania)', pg.evaluate('!!__bikerc.rec') and not pg.query_selector('.coach-cd'))
    pg.wait_for_timeout(13000)
    s2 = spoken(pg); print('   spoken so far:', s2)
    check('film: "Pomiar rozpoczęty"', any('Pomiar rozpoczęty' in s for s in s2))
    check('film: alert zakresu 140–155 (wyprost poza zakresem)', any('orientacyjnego zakresu' in s and 'Siodło' in s for s in s2))
    check('film: odczyt okresowy (wyprost + kadencja)', any('Wyprost kolana w dolnym punkcie' in s and 'Kadencja' in s for s in s2))
    pg.tap('#d-rec'); pg.wait_for_timeout(1500)
    s3 = spoken(pg); check('koniec: podsumowanie', any(s.startswith('Koniec pomiaru') and 'Maksymalny wyprost' in s for s in s3), str(s3[-1:]))
    pg.locator('#btn-pdf').scroll_into_view_if_needed(); pg.tap('#btn-pdf'); pg.wait_for_selector('#sheet:not([hidden])', timeout=60000); pg.wait_for_timeout(800)
    check('PDF gotowy – komunikat', any('Raport PDF gotowy' in s for s in spoken(pg)), str(spoken(pg)[-2:]))
    pg.evaluate('document.getElementById("sheet").hidden=true')
    # poziom minimalny: brak odczytów okresowych
    pg.evaluate('Coach.set({level:"minimal"}); window.__spoken.length=0')
    pg.tap('#d-rec'); pg.wait_for_timeout(500)
    # syntetyczna asymetria L–P (lewa ~150°, prawa ~135°) wstrzyknięta do bufora serii
    pg.evaluate('''()=>{const S=__bikerc; window.__asy=setInterval(()=>{const now=S.series.length?S.series[S.series.length-1].t:0,a=[];
      for(let t=now-20;t<=now;t+=.05) a.push({t,v:{knee_L:110+40*(.5+.5*Math.sin(6.283*t*1.5)),knee_R:100+35*(.5+.5*Math.sin(6.283*t*1.5))}}); S.series=a},200)}''')
    pg.wait_for_timeout(12500)
    pg.evaluate('clearInterval(window.__asy)')
    sm = spoken(pg)
    check('asymetria L–P: komunikat o różnicy stron', any('różnica między stronami' in s.lower() or 'Duża różnica' in s for s in sm), str(sm)); check('minimalny: brak odczytów co 10 s', not any('Kadencja:' in s for s in sm), str(sm))
    pg.tap('#d-rec'); pg.wait_for_timeout(1500)
    check('minimalny: podsumowanie nadal jest', any(s.startswith('Koniec pomiaru') for s in spoken(pg)))
    # ---- kamera: odliczanie 3-2-1 (świeża strona)
    pg.reload(wait_until='load'); pg.wait_for_timeout(1000)
    pg.evaluate('Coach.set({level:"normal"}); window.__spoken.length=0')
    pg.tap('#d-cam'); pg.wait_for_function('__bikerc.running&&__bikerc.source==="camera"', timeout=30000); pg.wait_for_timeout(1500)
    pg.evaluate('window.__spoken.length=0')
    pg.tap('#d-rec'); pg.wait_for_timeout(600)
    check('odliczanie widoczne na podglądzie', pg.query_selector('.coach-cd.on') is not None, pg.inner_text('.coach-cd') if pg.query_selector('.coach-cd') else '')
    pg.wait_for_timeout(4000)
    sc = spoken(pg); print('   countdown spoken:', sc)
    nums = [s for s in sc if s in ('3','2','1','Start')]
    check('odliczanie 3-2-1-Start po kolei', nums == ['3','2','1','Start'] , str(nums))
    check('po odliczaniu trwa pomiar', pg.evaluate('document.getElementById("d-rec").textContent').find('Koniec') >= 0)
    pg.tap('#d-rec'); pg.wait_for_timeout(800)
    # anulowanie odliczania
    pg.evaluate('window.__spoken.length=0'); pg.tap('#d-rec'); pg.wait_for_timeout(900); pg.tap('#d-rec'); pg.wait_for_timeout(3500)
    check('anulowanie odliczania nie startuje pomiaru', 'Koniec' not in pg.evaluate('document.getElementById("d-rec").textContent') and not pg.query_selector('.coach-cd.on'), pg.evaluate('document.getElementById("d-rec").textContent'))
    pg.screenshot(path=os.path.join(t.SHOTS, 'coach-bikerc.png'))
    pg.tap('#s-voicecfg'); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(t.SHOTS, 'coach-bikerc-panel.png')); pg.tap('#coach-close')
    # ---- utrata sylwetki (film bez człowieka)
    pg.reload(wait_until='load'); pg.wait_for_timeout(800); pg.evaluate('window.__spoken.length=0')
    with pg.expect_file_chooser() as fc: pg.tap('#d-film')
    blank = '/tmp/blank.mp4'
    if not os.path.exists(blank): os.system(f'ffmpeg -v error -y -f lavfi -i color=c=0x445566:s=640x480:d=14:r=25 -pix_fmt yuv420p {blank}')
    fc.value.set_files(blank); pg.wait_for_timeout(11000)
    sl = spoken(pg); check('brak sylwetki w kadrze: podpowiedź głosowa', any('Nie widzę sylwetki' in s for s in sl), str(sl))
    check('brak błędów JS/konsoli', not errs, '; '.join(errs)[:400])
    br.close()
print(f'\n{sum(res)}/{len(res)} PASS'); sys.exit(0 if all(res) else 1)
