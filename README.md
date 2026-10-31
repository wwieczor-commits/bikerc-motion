# BikeRc Motion – analiza ruchu z kamery (przeglądarka)

Autor i prawa autorskie: © Wojciech Wieczorek.

Statyczna aplikacja (bez build-stepu): `index.html` + `assets/`.
MediaPipe Tasks Vision PoseLandmarker działa w całości w przeglądarce – obraz nie jest nigdzie wysyłany.

## Uruchomienie
- Lokalnie: `python3 -m http.server 8000` → http://localhost:8000 (kamera działa na localhost i HTTPS).
- Można też otworzyć `index.html` bezpośrednio (file://) – Chrome/Edge pozwalają na kamerę.
- Hosting: wystarczy wgrać cały katalog (Firebase Hosting, GitHub Pages, dowolny serwer). Wymagane HTTPS.

## Biblioteka i model
Domyślnie z CDN (jsDelivr + storage.googleapis.com). Gdy CDN jest niedostępny, a strona jest serwowana przez http(s),
używane są kopie z `assets/mediapipe/` (wymuszenie: `?mp=local`). Aby odchudzić wdrożenie (~34 MB) można usunąć
`assets/mediapipe/` i polegać wyłącznie na CDN.

## Marka
Kolory i czcionki z www.bikerc.pl: tło #232222 / #1F1E1E / #2B2A2A, akcent #2EC4B6 (hover #6FDCD1), tekst #F2F4F3, szary #A9AFAE;
Archivo (nagłówki, italic 800/900) + Inter (tekst); logo `assets/logo-bikerc.svg` (pobrane z bikerc.pl).

## Eksport
- CSV szczegółowy: `time_s, knee_left, knee_right, hip_*, elbow_*, shoulder_*, ankle_*, torso_*, wrist_*`
- CSV „/pomiary”: `frame, timestamp_s, angle_0…angle_11` (kolejność jak w systemie /pomiary: bark, łokieć, nadgarstek, biodro, kolano, kostka; prawa=parzysty, lewa=nieparzysty indeks)
- JSON: metadane, statystyki, kąty i (opcjonalnie) 33 punkty na klatkę.

## Raport PDF

Po zakończeniu pomiaru aktywuje się przycisk **📄 Raport PDF** (karta „Eksport”). Raport A4 po polsku jest generowany w całości w przeglądarce (jsPDF, nic nie jest wysyłane):

- nagłówek z logo BikeRc, tytuł, data i godzina, klient, rower, czas pomiaru, analizowana strona, liczba próbek,
- dwie klatki z sylwetką i szkieletem (maks. wyprost i maks. zgięcie kolana),
- kluczowe wyniki: kolano maks./min, szacowana kadencja, średni szczyt wyprostu kolana,
- automatyczne obserwacje **orientacyjne** (wyprost kolana vs 140–155°, asymetria L–P, nachylenie tułowia, jakość pomiaru),
- tabela min / max / zakres / średnia dla lewej i prawej strony + różnica L–P,
- wykresy kąta w czasie: kolano, biodro, łokieć, tułów (wektorowe),
- stopka: bikerc.pl, numer strony, zastrzeżenie.

Biblioteki: `jspdf@2.5.2` z CDN (jsDelivr), fallback lokalny `assets/vendor/jspdf.umd.min.js`; czcionki Inter i Archivo (podzbiór z polskimi znakami, base64) w `assets/vendor/report-fonts.js`. Przykład: `sample/przykladowy-raport.pdf` (pomiar testowy z nagrania przysiadu, nie kolarstwa).

## Telefon (Android Chrome, iOS Safari)

**Najważniejsze: kamera w przeglądarce działa tylko przez HTTPS** (albo `localhost`). Plik otwarty z dysku telefonu lub adres `http://192.168.x.x` NIE uruchomi kamery – aplikacja pokaże wtedy komunikat. Dlatego aplikację trzeba wystawić pod adresem `https://…` (patrz „Hosting”).

- Start kamery wyłącznie z dotknięcia przycisku (wymóg iOS). Domyślnie **tylna** kamera na telefonie (trener filmuje zawodnika), przednia na komputerze; przełącznik 📷 Tylna / 🤳 Przednia oraz przycisk 🔄.
- Kolejność prób `getUserMedia`: wybrane urządzenie → `facingMode` + 1280×720 → 640×480 → samo `facingMode` → dowolna kamera (obsługa `OverconstrainedError`).
- Wydajność: model Lite, GPU z awaryjnym CPU, analiza ograniczana do ~25 kl./s (a przy wolnym telefonie ~12), płótno max 960 px, DPR ≤ 1,5, pauza po zejściu do tła, Wake Lock (ekran nie gaśnie).
- Interfejs: wideo na górze, stały dolny pasek (📷 Kamera / 🎬 Film / ● Pomiar / ⛶ Pełny; przełączanie przód/tył jest na obrazie), zwijane sekcje, pełny ekran (z awaryjnym „pełnym ekranem CSS” na iPhonie), układ pionowy i poziomy.
- PDF / CSV / JSON / PNG na telefonie: arkusz „Udostępnij / Otwórz / Pobierz” (Web Share API z plikiem, otwarcie blobu w nowej karcie, pobranie).
- PWA: `manifest.webmanifest` + `sw.js` – „Dodaj do ekranu głównego” (Android: przycisk ⬇ Zainstaluj; iOS: Udostępnij → Dodaj do ekranu początkowego). Offline działa powłoka aplikacji; model i biblioteki z CDN są cache’owane po pierwszym użyciu (na iOS pierwsze uruchomienie wymaga internetu).

### Film z telefonu (analiza nagrania)

- Przycisk **🎬 Film** w dolnym pasku, **„Wczytaj film z telefonu”** na ekranie startowym i **🎬 Wczytaj film** w ustawieniach (komputer). `<input type=file accept="video/*">` bez `capture` – telefon proponuje galerię/pliki. Link „Nagraj nowy film aparatem telefonu” używa drugiego inputa z `capture`.
- Odtwarzacz (tylko dla filmu): ▶/⏸, krok o klatkę ⏮ ⏭ (1/30 s), suwak przewijania, prędkość 0,25× / 0,5× / 1×.
- Pomiar, CSV/JSON i PDF działają na filmie; znaczniki czasu to **czas filmu** (nie zegar), więc wolne odtwarzanie nie zniekształca wyników. Koniec filmu kończy pomiar automatycznie.
- Format: MP4 (H.264) działa wszędzie. Filmy .mov/HEVC z iPhone’a mogą nie zadziałać w Chrome – aplikacja pokaże polski komunikat (iPhone: Ustawienia → Aparat → Formaty → „Najbardziej zgodne”).
- Aktualizacje PWA: `sw.js` (v4) pobiera `index.html` najpierw z sieci (z cache tylko offline), a nowa wersja przeładowuje aplikację automatycznie.

### Hosting (HTTPS)

Statyczny hosting wystarczy. Gotowy `firebase.json` (Firebase Hosting; ignoruje screenshots/sample/tests). Przykład (wymaga zalogowania – `firebase login` – i projektu Firebase):

```
cp .firebaserc.example .firebaserc      # wpisz id projektu
npx firebase-tools hosting:sites:create bikerc-motion   # osobna witryna, żeby nie nadpisać bikerc-5a1dd.web.app
npx firebase-tools deploy --only hosting
```

Szybki test na telefonie bez wdrożenia (tymczasowy tunel HTTPS, wymaga pobrania `cloudflared`):

```
python3 -m http.server 8765 &
cloudflared tunnel --url http://localhost:8765     # wypisze https://xxxx.trycloudflare.com
```

### Testy

`python3 tests/test_mobile.py http://localhost:8765/index.html` – emulacja Pixel 7 i iPhone 13 (pion/poziom), kamera testowa, PDF, PWA offline, komunikat o HTTPS.
