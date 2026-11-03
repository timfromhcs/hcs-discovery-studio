# Von Null auf Hundert — HCS Discovery Studio (Deutsch)

Ein kompletter erster Tag, in der richtigen Reihenfolge. Jeder Befehl und jede
Aussage hier ist überprüfbar. Wenn etwas nicht reproduzierbar ist, ist das ein
Fehler in dieser Anleitung — keine „bekannte Einschränkung".

> **Was das ist**: eine offene, lokale Workbench für computergestützte
> Wirkstoffforschung. Bibliothek importieren, mit transparenten Regeln triagieren,
> Ähnlichkeit bewerten (CPU oder GPU), mit AutoDock Vina docken (wenn installiert),
> jede Zeile und jedes Ereignis prüfen, Bericht exportieren.
>
> **Was das nicht ist**: ein klinisches Entscheidungssystem, ein zugelassenes
> Medizinprodukt oder ein Beleg für Bindung, Sicherheit oder Wirksamkeit. Rankings
> sind Priorisierungssignale.

---

## 1. Wie willst du es starten?

| Ziel | Weg | Zeit |
|---|---|---|
| Nichts installieren, nur ansehen | gehosteter statischer Build (nur Offline-Labor, kein Backend) | 1 Min |
| Echte lokale Workbench | Ein-Datei-Programm oder Wheel | 3 Min |
| Server / anderer Rechner | Docker-Image | 5 Min |
| Entwickeln | Quellcode mit `uv` und Node | 10 Min |

### A — Ein-Datei-Programm (Windows)

```powershell
uv pip install "pyinstaller==6.22.3"     # nur zum Bauen, nicht im Lockfile
uv run python scripts/release/build_executable.py
build\exe-dist\hcs-discovery.exe doctor
build\exe-dist\hcs-discovery.exe serve
```

Dann <http://127.0.0.1:8787> öffnen. Der Server enthält einen Worker, Läufe starten
also ohne zweiten Prozess.

### B — Wheel

```bash
python -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\Activate.ps1
pip install hcs_discovery_studio-2.0.0-py3-none-any.whl
hcs-discovery doctor
hcs-discovery serve
```

### C — Docker

```bash
export HCS_API_TOKEN=$(openssl rand -hex 24)
docker compose up --build
curl -H "Authorization: Bearer $HCS_API_TOKEN" http://127.0.0.1:8787/api/v1/health
```

Die API verweigert eine Bindung an Nicht-Loopback ohne Token — absichtlich. Vor
öffentlichem Betrieb einen TLS-Proxy davorsetzen.

### D — Quellcode

```bash
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
uv sync --dev
cd apps/web && npm ci && npm run build && cd ../..
uv run hcs-discovery serve
```

---

## 2. Erstes Projekt, erster Lauf (CLI)

```bash
hcs-discovery project create --name "Demo-Projekt"
hcs-discovery dataset import examples/datasets/demo_library.csv --project <projekt-id>
hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <projekt-id> --dataset <dataset-id>
hcs-discovery run status <run-id>
hcs-discovery report export <run-id> --format html --output bericht.html
```

Was passiert ist: Die Datei wurde Zeile für Zeile gelesen (16 von 17 importiert,
das Duplikat bleibt mit Begründung sichtbar), RDKit hat die Strukturen
standardisiert, der Workflow hat Deskriptoren berechnet, Zeilen anhand der
Schwellen markiert, die Überlebenden gerankt und eine Zusammenfassung geschrieben.
Jeder Knoten, jedes Ereignis und jedes Artefakt steht im Lauf.

`--json` vor oder nach jedem Unterbefehl liefert maschinenlesbare Ausgabe.

---

## 3. Ähnlichkeitssuche (CPU, GPU oder beides)

```bash
hcs-discovery similarity search --query "CC(=O)Oc1ccccc1C(=O)O" \
  --file examples/datasets/demo_library.csv --k 10

hcs-discovery similarity search --query "c1ccccc1" --file library.csv \
  --engine gpu --boost auto --threshold 0.7 --output scores.csv --json
```

- `--engine auto` nutzt eine Hardware-GPU, wenn vorhanden, sonst die CPU-Referenz.
- `--engine gpu` **scheitert** (Exit-Code 3), wenn kein Hardware-Adapter existiert,
  statt still auf die CPU zu wechseln.
- Auf der GPU werden die ganzzahligen Popcounts vor der Ausgabe gegen die
  CPU-Referenz geprüft. Eine Abweichung ist ein Fehler, keine „etwas andere Zahl".
- `--boost hybrid` teilt die Bibliothek zwischen GPU und CPU-Threads auf. Das ist
  gemessen, nicht versprochen: siehe `docs/validation/gpu-tanimoto.md`.

`hcs-discovery gpu probe` zeigt den Adapter, `hcs-discovery gpu bench` misst
Parität und Durchsatz auf *deiner* Maschine neu.

---

## 4. Das Offline-Labor (ganz ohne Server)

`/lab` in der Oberfläche öffnen (oder im gehosteten statischen Build).

1. CSV mit `smiles`-Spalte, `.smi` oder `.sdf` importieren.
2. RDKit WebAssembly berechnet die Deskriptoren **im Browser**.
3. Die Seite triagiert und rankt mit denselben Regeln und Gewichten wie die
   Server-Vorlage und schreibt dazu, dass der Score datensatzrelativ ist.
4. „Score library" startet die Tanimoto-Suche über WebGPU — oder die CPU-Referenz,
   falls Browser/Gerät keinen Adapter haben; das wird benannt.
5. Die gespeicherte Kopie liegt in IndexedDB auf diesem Gerät. „Delete stored copy"
   löscht sie wirklich. Nichts wird hochgeladen.

Dieser Modus funktioniert auf dem Handy, im Flugzeug und auf einem statischen Host
ohne Backend.

---

## 5. Automatisierung: API, MCP, Workflows

**HTTP-API** — versioniert unter `/api/v1`, OpenAPI unter `/api/v1/openapi.json`.

```bash
curl -X POST http://127.0.0.1:8787/api/v1/similarity/search \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"<id>","query_smiles":"c1ccccc1","k":5,"engine":"cpu"}'
```

**MCP** — für lokale KI-Assistenten:

```bash
hcs-discovery mcp serve     # JSON-RPC 2.0 über stdin/stdout
```

Werkzeuge: `hcs_doctor`, `hcs_similarity_search`, `hcs_gpu_bench`,
`hcs_workflow_validate`, `hcs_models_list`. Nur lesend, begrenzte Eingaben, keine
Shell.

**Constraint-Auswahl (SAT)**:

```bash
hcs-discovery sat select --group "niedrig=a,b" --group "mittel=c,d" --k-max 2
hcs-discovery sat solve --cnf formel.cnf     # Exit 5 = unerfüllbar
```

---

## 6. Wenn etwas falsch aussieht

| Symptom | Prüfen |
|---|---|
| „frontend not built" | `cd apps/web && npm ci && npm run build` |
| `program not found: hcs` | Der Befehl heißt `hcs-discovery`. |
| Bindung an 0.0.0.0 verweigert | `HCS_API_TOKEN` setzen; TLS macht der Proxy. |
| GPU wird nicht genutzt | `hcs-discovery gpu probe`; Software-Adapter werden bewusst ignoriert. |
| GPU-Paritätsfehler | Das ist ein echter Fehler — das Ergebnis wird zurückgehalten. Mit Adaptername melden. |
| Browser-Chemie schlägt fehl | Die CSP muss `'wasm-unsafe-eval'` und `'unsafe-eval'` erlauben; die App setzt das selbst. |
| E2E-Portkonflikt | Playwright nutzt 8791 (Backend) und 8792 (statisch); andere Server stoppen. |

`hcs-discovery doctor` beantwortet die meisten davon auf einmal.

---

## 7. Die Ehrlichkeits-Checkliste

Bevor du eine Zahl aus diesem Projekt zitierst, prüfe, welche Art Zahl es ist:

- **Auf diesem Host gemessen** (ein Bericht in `docs/validation/` nennt die Hardware).
- **In CI verifiziert** (Link zum Lauf in `docs/engineering/IMPLEMENTATION_STATUS.md`).
- **Geplant** (Registry-Karte `planned`; nicht ausführbar).
- **Schwach und so benannt** (ESOL RMSE ≈ 0,97 und R² ≈ 0,07 — kaum besser als eine
  Konstante).

Passt eine Aussage in keine dieser Kategorien, ist es ein Dokumentationsfehler.
Bitte ein Issue öffnen.
