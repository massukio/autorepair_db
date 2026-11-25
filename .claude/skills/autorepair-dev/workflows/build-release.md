# Build, test on Windows, release

## Versioning and identity

- `app/config.py`: `APP_NAME = "汽車保養資料庫"`, `APP_VERSION`, `APP_RELEASE_DATE`,
  `APP_AUTHOR = "Sukio Lin"`, `APP_CREATED_YEAR = 2026`, MIT license. These feed
  the window title, header and the 設定 → 關於本程式 card.
- First public release is **1.0.0** (owner decision). Bump with semver:
  patch for fixes, minor for features. Only bump when the owner releases.
- Exe name comes from `autorepair.spec` (`name="汽車保養資料庫"`). If you rename
  it, old copies stay in users' folders — tell the owner.

## Icon

Source: `assets/icon_source.jpg` (blue rounded square on white). `tools/make_icon.py`
crops it, makes the corners transparent and writes `assets/app.ico` (16–256 px)
and `assets/app.png`. Both are generated at build time and gitignored. To change
the icon, replace the source image and rebuild.

## Build (on Windows)

`build_exe.bat` = pip install -r requirements.txt → pytest → make_icon → PyInstaller.
Output: `dist\汽車保養資料庫.exe` (~38 MB, onefile, starts in a few seconds).
Keep `build_exe.bat` **CRLF and ASCII-only** (`.gitattributes` enforces CRLF);
UTF-8 Chinese or LF line endings break cmd.exe parsing.

## Windows test machine

A Windows 11 VM is used for builds and real-rendering checks. Host, user and
password are NOT stored in this public repo: read them from
`AUTOREPAIR_WIN_HOST` / `AUTOREPAIR_WIN_USER` / `AUTOREPAIR_WIN_PASS`, or ask the
owner. Python 3.12 is installed per-user at
`%LOCALAPPDATA%\Programs\Python\Python312` (prepend it and `Scripts` to PATH).
No git there: upload a tarball of the working tree (exclude `.git`, `.claude`,
caches), `tar -xzf` it, run `build_exe.bat`.

Proven loop (from macOS/Linux with `sshpass`):
1. `COPYFILE_DISABLE=1 tar --exclude=.git --exclude=.claude --exclude=__pycache__ -czf src.tgz autorepair`
   (`COPYFILE_DISABLE=1` stops macOS adding `._*` metadata files)
2. `scp src.tgz` → `ssh "... tar -xzf src.tgz && cd autorepair && set PATH=...;%PATH% && build_exe.bat > build.log 2>&1"`
   then `findstr "passed FAILED Build OK" build.log`.
3. Replace the test copy: stop running app processes, copy `dist\*.exe` into the
   test folder (a path with Chinese characters and spaces, to keep testing that),
   relaunch.
4. GUI programs started over SSH run in session 0 (invisible). To launch or
   screenshot inside the logged-in desktop, create a scheduled task with
   `schtasks /Create /RU <user> /IT` that runs `wscript hidden.vbs <script.ps1>`
   and `schtasks /Run` it.
5. Screenshot the app window with `PrintWindow` (user32) on the app's
   `MainWindowHandle`; full-screen `CopyFromScreen` returns a frozen frame on
   the VM. Write PowerShell scripts containing Chinese as **UTF-16LE with BOM**.
6. Check the embedded exe icon with
   `[System.Drawing.Icon]::ExtractAssociatedIcon($exe)`.

Single-instance check: launching a second copy must only show 「…已經開著了」
(`QLockFile` in `start.py`); close those test dialogs afterwards.

Gotchas (2026-11-24): give `scp` an absolute `C:/Users/<user>/...` destination
(a relative one failed); `findstr` with Chinese in a cmd `&&` chain fails and
silently stops the chain; send PowerShell as a UTF-16LE+BOM `.ps1` file instead
of quoting through ssh. Release zip: build it on Windows with .NET
`ZipFile.CreateFromDirectory(..., UTF8)` so the Chinese exe name has the UTF-8
flag (check `flag_bits & 0x800` with Python); deliver as
`dist/汽車保養資料庫_<version>.zip` (dist/ is gitignored).

Gotchas: the SSH server sometimes rejects the password after many quick
connections — wait and retry; a dropped `scp` means the remote still has the old
source (check timestamps before trusting a "Build OK"); `Copy-Item` fails while
the old exe is still exiting — retry after a second. Explorer caches icons per
path: a rebuilt exe at the same path may show the old icon (`ie4uinit -show`,
F5, or rename to confirm).

## Release checklist

1. Tests pass; screenshots reviewed; `tools/bench.py` within budgets.
2. Version/date in `app/config.py`; README updated.
3. Build on Windows; run the exe from a folder with Chinese characters and
   spaces; check every page; backup → restore round trip; PDF export opens.
4. Commit; push only when the owner asks (GitHub over HTTPS if SSH port 22 is
   blocked: `git push https://github.com/massukio/autorepair_db.git main`).
5. Deliver `dist\汽車保養資料庫.exe`. Users keep the exe and `汽車保養資料`
   folder together; upgrading = replace the exe only.

## Manual screenshots (tools/make_manual.py) — run on Windows

- Offscreen Qt on Windows has NO system fonts unless told where they are:
  `$env:QT_QPA_PLATFORM="offscreen"; $env:QT_QPA_FONTDIR="C:\Windows\Fonts"`.
  The windows platform over SSH (session 0) works but its screen is 1024×768, so
  windows are squeezed — use offscreen + QT_QPA_FONTDIR (1280×900 pictures).
- Point the data dir env var at an EMPTY folder with a natural Chinese path
  (e.g. `C:\汽車保養資料庫\汽車保養資料`): the 備份/還原 picture shows it. Delete it after.
- Copy the PNGs back into the repo (they are committed) and build: the spec bundles
  `assets/manual`. Check a running exe: `%TEMP%\_MEI*\assets\manual` holds the files.
- VM automation: injected mouse/keys do nothing while the VM's desktop session is
  disconnected (PrintWindow still works). In PowerShell, `$null` passed to a string
  parameter becomes "" — use `[NullString]::Value` (e.g. `FindWindow`).

## Release zip (owner rule, 2026-11-25)

`build_exe.bat` ends with `tools/make_release.py`, which writes
`dist/<APP_NAME>_<APP_VERSION>.zip` = ONE folder `<APP_NAME>_<APP_VERSION>/` with exactly
two files: the exe and `使用說明書.html` (the in-app manual as a single file, pictures
embedded as data URIs, opens in any browser). It verifies the zip and fails the build
otherwise; Python's zipfile sets the UTF-8 flag for the Chinese names. Deliver that
zip as built — do not hand-pack zips in PowerShell any more (older notes above).
`test_release_zip_is_one_folder_with_exe_and_manual` guards the layout.
