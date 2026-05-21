# One-Click Deployment Packages Design

## Scope

Deliver 4 distribution packages (Windows light, Windows full, Linux light, Linux full) generated from the `simpleQQbot/` source tree by a build script, plus a rewritten README oriented around one-click deployment.

## Package Matrix

| | Light | Full (self-contained) |
|---|---|---|
| **Windows** | Source + scripts; user installs Python & NapCat | Python embed + NapCat binary + offline wheels; extract & run |
| **Linux** | Source + install.sh; system package manager fetches deps | NapCat binary + offline wheels; `install.sh --offline`, no network needed |

## Directory Layout

```
project/
├── simpleQQbot/              # Development repo (unchanged role)
└── simpleQQbot-dist/         # NEW: packaging workspace
    ├── build.sh              # Generate one or all packages
    ├── patch/
    │   ├── windows/
    │   │   ├── start.bat
    │   │   ├── setup.bat
    │   │   └── README.md     # In-package simplified README
    │   └── linux/
    │       └── install.sh    # Already exists; add --offline support
    ├── vendor/
    │   ├── get-pip.py        # Bootstrap pip for Python embed
    │   └── python-embed/     # Download cache for Windows Python embed
    └── artifacts/            # Generated packages (gitignored)
        ├── qqbot-windows-light.zip
        ├── qqbot-windows-full.zip
        ├── qqbot-linux-light.tar.gz
        └── qqbot-linux-full.tar.gz
```

`build.sh` reads from `../simpleQQbot/`, copies source, prunes dev-only files, injects platform-specific scripts and vendor deps, then packages.

## Pruning Rules (applied to all packages)

Exclude: `.git`, `__pycache__`, `*.pyc`, `.venv`, `.env`, `data/*.db*`, `.claude/`, `.pytest_cache/`, `.idea/`, `.vscode/`, `release/`, `docs/superpowers/`, `tests/`, `napcat/` (runtime data), `.dockerignore`, `Dockerfile`, `docker-compose.yml`

Replace: `.env.example` ships; `config/permissions.yaml` ships with empty admins.

## Package Contents

### Windows Light (`qqbot-windows-light.zip`)

```
qqbot/
├── start.bat
├── setup.bat
├── bot.py, pyproject.toml, .env.example
├── config/  (personalities.yaml, permissions.yaml)
├── lib/     (all .py, stripped of cache)
├── src/     (plugins)
└── README.md
```

User must have Python 3.11+ on PATH. `start.bat` checks `.env` exists, checks venv exists, guides NapCat download.

### Windows Full (`qqbot-windows-full.zip`)

Windows-light contents PLUS:

```
qqbot/
├── python/          # Python 3.11.x embeddable + get-pip.py
├── wheels/          # All pyproject.toml deps as .whl files
└── napcat/          # NapCat Windows binary + config template
```

`setup.bat`: creates venv from embedded Python, bootstraps pip, then `pip install --no-index --find-links=wheels/ -e .`

`start.bat`: after setup, launches both `python bot.py` and `napcat/napcat.exe` (or prompts user to start NapCat separately).

### Linux Light (`qqbot-linux-light.tar.gz`)

```
qqbot/
├── install.sh       # Current install.sh (interactive, network-required)
├── bot.py, pyproject.toml, .env.example
├── config/, lib/, src/
└── README.md
```

`bash install.sh` handles: system deps → venv → pip install → NapCat download → systemd services.

### Linux Full (`qqbot-linux-full.tar.gz`)

Linux-light contents PLUS:

```
qqbot/
├── wheels/          # pip wheels cache for offline install
└── napcat/
    ├── napcat-linux-amd64.tar.gz
    └── napcat-linux-arm64.tar.gz
```

`bash install.sh --offline`: skips system package manager (assumes python3 present), installs pip deps from `wheels/`, extracts NapCat binary matching current arch, configures systemd.

## Script Behaviors

### Windows `start.bat`

```
1. Check .env exists
   - No  → echo "edit .env.example first" → notepad .env.example → exit
   - Yes → continue
2. Check .venv\Scripts\python.exe
   - No  → call setup.bat
   - Yes → continue
3. Check NapCat present (full pack: napcat/ dir; light pack: prompt manual download)
4. Start python bot.py in foreground
5. Print "Bot started. Open another terminal and run napcat to log in."
```

### Windows `setup.bat`

```
Light variant:
  python -m venv .venv
  .venv\Scripts\pip install -e .

Full variant:
  python\python.exe -m venv .venv
  .venv\Scripts\python.exe python\get-pip.py --no-index --find-links=wheels\
  .venv\Scripts\pip install --no-index --find-links=wheels\ -e .
```

### Linux `install.sh` changes

Add `--offline` flag:
- Skips `install_system_deps()` (trusts python3 pre-installed)
- Skips `install_napcat()` download step (extracts from local tarball instead)
- In `setup_venv()`: `pip install --no-index --find-links=wheels/ -e .`
- No `wget` call; NapCat extracted from bundled archive

## build.sh Implementation

Single bash script in `simpleQQbot-dist/`. Key logic:

```bash
# Usage: bash build.sh [windows-light|windows-full|linux-light|linux-full|all]

build_common() {
    rsync -a --exclude=... ../simpleQQbot/ ./build/
    # apply pruning excludes
}

build_windows_light() {
    build_common
    cp patch/windows/start.bat patch/windows/setup.bat patch/windows/README.md build/
    (cd build && zip -r ../artifacts/qqbot-windows-light.zip .)
}

build_windows_full() {
    build_windows_light
    cp -r vendor/python-embed build/python
    pip download -d build/wheels/ --python-version 3.11 ... (all pyproject deps)
    # download NapCat Windows binary
    cp patch/napcat/onebot11_template.json build/napcat/
    (cd build && zip -r ../artifacts/qqbot-windows-full.zip .)
}
# ... linux variants analogous
```

### Prerequisites for running build.sh

- `rsync`, `zip`, `tar` available
- Python 3.11+ with pip (for `pip download`)
- Network access (for downloading NapCat binaries + pip wheels during build)

## README Rewrite

### Principles

- Target audience: non-developers who want an AI QQ bot
- Remove all manual-install procedural steps (python venv, pip, Lagrange config, etc.)
- Lead with package downloads, not with source code
- Keep full config reference, command list, error codes, FAQ

### New Structure

1. **简介** — 2 sentences, what this is
2. **功能** — bullet list (preserved, trimmed)
3. **快速开始** — 4-line per-platform guide pointing at packages
4. **选择哪个包？** — table: light vs full tradeoffs per OS, with recommendations
5. **配置**
   - `.env` 完整配置参考 (preserved)
   - `permissions.yaml` (preserved)
   - `personalities.yaml` (preserved)
6. **指令列表** (preserved)
7. **错误码** (preserved)
8. **常见问题** — updated: add package-specific FAQs, remove venv/Python install questions
9. **Docker 部署** — brief section, one command
10. **项目结构** — updated
11. **开发指南** — link to source repo

### Deleted Content

- ~150 lines of Windows 9-step manual deployment (Steps 1–9 in current README)
- "什么是 API Key?" / "什么是 API Base?" (move to config section as tooltips)
- Old Lagrange OneBot setup instructions

## Deliverables

1. `simpleQQbot-dist/` directory with `build.sh`, `patch/`, `vendor/`, `artifacts/` (gitignored)
2. `simpleQQbot-dist/patch/windows/start.bat`, `setup.bat`, `README.md`
3. `simpleQQbot-dist/patch/linux/install.sh` (copy + enhance existing `scripts/install.sh`)
4. Rewritten `README.md` in `simpleQQbot/`
5. `.gitignore` in `simpleQQbot-dist/` excludes `artifacts/` and `vendor/python-embed/`

## Location Decision

`simpleQQbot-dist/` lives as a sibling directory to `simpleQQbot/` (as shown in Directory Layout above). User confirmed this layout. `build.sh` references source via `../simpleQQbot/`, and `artifacts/` is gitignored within `simpleQQbot-dist/`'s own `.gitignore`.
