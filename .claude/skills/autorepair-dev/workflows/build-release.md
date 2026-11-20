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
1. `tar --exclude=.git --exclude=.claude --exclude=__pycache__ -czf src.tgz autorepair`
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
5. Deliver `dist\汽車保養資料庫.exe`. Users keep the exe and `autorepair_data`
   folder together; upgrading = replace the exe only.
