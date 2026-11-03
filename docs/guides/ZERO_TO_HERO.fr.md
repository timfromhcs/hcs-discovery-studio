# De zéro à héros — HCS Discovery Studio (Français)

Une première journée complète, dans l'ordre. Chaque commande et chaque affirmation
ici sont vérifiables. Si quelque chose ne se reproduit pas, c'est un défaut de ce
guide, pas une « limitation connue ».

> **Ce que c'est** : un atelier ouvert et local pour la découverte de médicaments
> assistée par ordinateur. Importer une chimiothèque, la trier avec des règles
> transparentes, calculer une similarité (CPU ou GPU), docker avec AutoDock Vina si
> installé, inspecter chaque ligne et chaque événement, exporter un rapport.
>
> **Ce que ce n'est pas** : un système de décision clinique, un dispositif homologué,
> ni une preuve de liaison, de sécurité ou d'efficacité. Les classements sont des
> signaux de priorisation.

---

## 1. Choisir le mode d'exécution

| Objectif | Moyen | Durée |
|---|---|---|
| Rien installer, juste regarder | build statique hébergé (labo hors ligne uniquement, sans backend) | 1 min |
| Un vrai atelier local | exécutable unique ou wheel | 3 min |
| Serveur / autre machine | image Docker | 5 min |
| Développer | sources avec `uv` et Node | 10 min |

### A — Exécutable unique (Windows)

```powershell
uv pip install "pyinstaller==6.22.3"     # outil de build, absent du lockfile
uv run python scripts/release/build_executable.py
build\exe-dist\hcs-discovery.exe doctor
build\exe-dist\hcs-discovery.exe serve
```

Ouvrir <http://127.0.0.1:8787>. Le serveur embarque un worker : les exécutions
démarrent sans second processus.

### B — Wheel

```bash
python -m venv .venv
. .venv/bin/activate           # Windows : .venv\Scripts\Activate.ps1
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

L'API refuse une écoute non-loopback sans jeton — c'est volontaire. Placez un proxy
TLS devant avant toute exposition publique.

### D — Sources

```bash
git clone https://github.com/timfromhcs/hcs-discovery-studio.git
cd hcs-discovery-studio
uv sync --dev
cd apps/web && npm ci && npm run build && cd ../..
uv run hcs-discovery serve
```

---

## 2. Premier projet, première exécution (CLI)

```bash
hcs-discovery project create --name "Projet démo"
hcs-discovery dataset import examples/datasets/demo_library.csv --project <id-projet>
hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <id-projet> --dataset <id-jeu>
hcs-discovery run status <id-execution>
hcs-discovery report export <id-execution> --format html --output rapport.html
```

Ce qui s'est passé : le fichier a été lu ligne par ligne (16 lignes sur 17
importées ; le doublon reste visible avec sa raison), RDKit a standardisé les
structures, le workflow a calculé les descripteurs, marqué les lignes selon les
seuils, classé les survivantes et écrit un résumé. Chaque nœud, événement et
artefact figure dans l'exécution.

`--json` avant ou après chaque sous-commande donne une sortie lisible par machine.

---

## 3. Recherche de similarité (CPU, GPU, ou les deux)

```bash
hcs-discovery similarity search --query "CC(=O)Oc1ccccc1C(=O)O" \
  --file examples/datasets/demo_library.csv --k 10

hcs-discovery similarity search --query "c1ccccc1" --file library.csv \
  --engine gpu --boost auto --threshold 0.7 --output scores.csv --json
```

- `--engine auto` utilise une GPU matérielle si présente, sinon la référence CPU.
- `--engine gpu` **échoue** (code 3) sans adaptateur matériel au lieu de basculer
  silencieusement.
- Sur GPU, les popcounts entiers sont comparés à la référence CPU avant tout
  résultat. Une divergence est une erreur, pas un nombre « légèrement différent ».
- `--boost hybrid` répartit la chimiothèque entre GPU et threads CPU. C'est mesuré,
  pas promis : voir `docs/validation/gpu-tanimoto.md`.

`hcs-discovery gpu probe` affiche l'adaptateur ; `hcs-discovery gpu bench` remesure
la parité et le débit sur *votre* machine.

---

## 4. Le labo hors ligne (sans serveur)

Ouvrir `/lab` dans l'interface (ou le build statique hébergé).

1. Importer un CSV avec une colonne `smiles`, un `.smi` ou un `.sdf`.
2. RDKit WebAssembly calcule les descripteurs **dans le navigateur**.
3. La page trie et classe avec les mêmes règles et poids que le modèle serveur, et
   indique que le score est relatif au jeu de données.
4. « Score library » lance la similarité Tanimoto via WebGPU — ou la référence CPU
   si l'appareil n'a pas d'adaptateur, et le dit.
5. La copie stockée vit dans IndexedDB sur cet appareil. « Delete stored copy » la
   supprime réellement. Rien n'est téléversé.

Ce mode fonctionne sur téléphone, hors connexion, et sur un hébergement statique
sans backend.

---

## 5. Automatisation : API, MCP, workflows

**API HTTP** — versionnée sous `/api/v1`, OpenAPI sur `/api/v1/openapi.json`.

```bash
curl -X POST http://127.0.0.1:8787/api/v1/similarity/search \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"<id>","query_smiles":"c1ccccc1","k":5,"engine":"cpu"}'
```

**MCP** — pour les assistants locaux :

```bash
hcs-discovery mcp serve     # JSON-RPC 2.0 sur stdin/stdout
```

Outils : `hcs_doctor`, `hcs_similarity_search`, `hcs_gpu_bench`,
`hcs_workflow_validate`, `hcs_models_list`. Lecture seule, entrées bornées, pas de
shell.

**Sélection sous contraintes (SAT)** :

```bash
hcs-discovery sat select --group "bas=a,b" --group "moyen=c,d" --k-max 2
hcs-discovery sat solve --cnf formule.cnf     # code 5 = insatisfiable
```

---

## 6. En cas de problème

| Symptôme | Vérifier |
|---|---|
| « frontend not built » | `cd apps/web && npm ci && npm run build` |
| `program not found: hcs` | La commande est `hcs-discovery`. |
| Écoute 0.0.0.0 refusée | Définir `HCS_API_TOKEN` ; le TLS est du ressort du proxy. |
| GPU non utilisée | `hcs-discovery gpu probe` ; les adaptateurs logiciels sont ignorés exprès. |
| Échec de parité GPU | C'est un vrai échec — le résultat est retenu. Signaler avec le nom de l'adaptateur. |
| Chimie navigateur en échec | La CSP doit autoriser `'wasm-unsafe-eval'` et `'unsafe-eval'` ; l'app les définit. |
| Conflit de port E2E | Playwright utilise 8791 (backend) et 8792 (statique) ; arrêter les autres serveurs. |

`hcs-discovery doctor` répond à la plupart de ces questions d'un coup.

---

## 7. La liste d'honnêteté

Avant de citer un chiffre de ce projet, vérifiez de quel type il s'agit :

- **Mesuré sur cet hôte** (un rapport dans `docs/validation/` nomme le matériel).
- **Vérifié en CI** (lien vers l'exécution dans `docs/engineering/IMPLEMENTATION_STATUS.md`).
- **Prévu** (carte de registre `planned` ; non exécutable).
- **Faible et annoncé comme tel** (ESOL RMSE ≈ 0,97 et R² ≈ 0,07 — à peine mieux
  qu'une constante).

Si une affirmation n'entre dans aucune catégorie, c'est un défaut de documentation.
Ouvrez une issue.
