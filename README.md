# Gemini Web-UI Automation Wrapper (Extended Edition)

> **Base Repository & Credits**: Ce projet est basé sur le dépôt open-source [`czarflix/GeminiCustomAPI`](https://github.com/czarflix/GeminiCustomAPI) (MIT License, Copyright (c) 2025 Gemini Custom API Contributors).  
> Tous les crédits de l'architecture Playwright originale reviennent à l'auteur original.

Cette extension apporte une surcouche **ultra-légère, universelle et rapide** permettant d'exploiter Gemini Web en génération d'image, vision, et édition d'image multimodal (Image-to-Image / Prompt-to-Image) sans réécriture lourde.

---

## 🚀 Nouvelles fonctionnalités ajoutées

### 1. Prise en charge universelle (3 modes fluides)
* **Cas 1 (Prompt seul) :** Saisie du texte dans le champ Gemini -> Génération de l'image (ou réponse texte) enregistrée directement sur disque.
* **Cas 2 (Image seule) :** Upload de l'image sur l'interface Gemini -> Envoi sans texte -> Récupération de l'image / analyse.
* **Cas 3 (Image + Prompt) :** Upload de l'image source ET saisie du prompt d'instruction (ex: *"transforme cette photo en style anime manga"*) -> Envoi -> Récupération automatique de l'image modifiée.

### 2. Interfaces d'entrée minimales (Node.js & Python au choix)
* **CLI Ultra-rapide Node.js :**
  ```bash
  node index.js --prompt "un chat mignon" --image "./input.png" --out "./output.png"
  ```
* **Serveur Web minimaliste Express :**
  Un seul fichier et endpoint `POST /` acceptant un prompt et/ou un fichier image et renvoyant directement le flux binaire de l'image générée :
  ```bash
  node index.js --server --port 3000
  ```
* **CLI & API Python (Parité complète) :**
  ```bash
  python cli.py --prompt "un chat mignon" --image "./input.png" --out "./output.png"
  ```
  Le serveur FastAPI d'origine (`python main.py`) propose également le nouvel endpoint `POST /` renvoyant le résultat binaire.

### 3. Session persistante unique (`user_data` / `storage`)
Le profil Chromium est conservé localement. Vous ne vous authentifiez qu'une seule fois avec votre compte Google, et la session est réutilisée automatiquement par toutes les requêtes CLI et API sans reconnexion.

---

## 📦 Installation rapide

### Option A : Environnement Node.js (Recommandé pour `node index.js`)

1. Installer les dépendances :
```bash
npm install
```
2. Installer Chromium pour Playwright (si pas déjà fait) :
```bash
npx playwright install chromium
```

### Option B : Environnement Python

1. Installer les dépendances :
```bash
pip install -r requirements.txt
playwright install chromium
```
2. Copier le fichier de configuration :
```bash
cp .env.example .env
```

---

## 🔑 Authentification initiale (À faire 1 seule fois)

Lancez l'assistant de connexion pour ouvrir un navigateur visible :

* **En Node.js :**
  ```bash
  npm run login
  # ou
  node index.js --login
  ```
* **En Python :**
  ```bash
  python login_helper.py
  ```

Connectez-vous à votre compte Google et vérifiez que vous accédez à Gemini, puis fermez le navigateur. Votre session est sauvegardée dans `./storage/playwright_profile` ou `./user_data`.

---

## 💻 Utilisation CLI

### Cas 1 : Prompt seul (Génération d'image ou texte)
```bash
node index.js --prompt "Un astronaute explorant une jungle extraterrestre fluorescente" --out "./mars.png"
```
*(ou en Python : `python cli.py --prompt "..." --out "./mars.png"`)*

### Cas 2 : Image seule (Upload direct sans prompt)
```bash
node index.js --image "./photo.png" --out "./result.png"
```
*(ou en Python : `python cli.py --image "./photo.png" --out "./result.png"`)*

### Cas 3 : Image + Prompt (Édition / Modification d'image)
```bash
node index.js --image "./portrait.png" --prompt "transforme cette photo en style anime cyberpunk" --out "./cyberpunk.png"
```
*(ou en Python : `python cli.py --image "./portrait.png" --prompt "..." --out "./cyberpunk.png"`)*

### Options du CLI
| Option | Raccourci | Description | Défaut |
|---|---|---|---|
| `--prompt` | `-p` | Texte du prompt ou instruction | `null` |
| `--image` | `-i` | Chemin de l'image locale à envoyer | `null` |
| `--out` | `-o` | Chemin du fichier de sortie généré | `./output.png` |
| `--server` | `-s` | Démarre le serveur Express léger | `false` |
| `--port` | | Port du serveur | `3000` |
| `--no-headless` | `--headful` | Affiche la fenêtre du navigateur (debug) | `headless` |
| `--login` | | Ouvre le navigateur pour se connecter à Google | |

---

## 🌐 Utilisation Serveur Web (Endpoint minimaliste `POST /`)

### Démarrer le serveur Express (Node.js) :
```bash
node index.js --server --port 3000
```

### Démarrer le serveur FastAPI (Python d'origine) :
```bash
python main.py
# ou uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Requête avec cURL (réception de l'image binaire directe) :
```bash
# Cas 3 : Image + Prompt
curl -X POST http://localhost:3000/ \
  -F "prompt=transforme cette photo en style aquarelle" \
  -F "image=@./portrait.png" \
  --output ./aquarelle.png

# Cas 1 : Prompt seul
curl -X POST http://localhost:3000/ \
  -F "prompt=un paysage futuriste sous la pluie" \
  --output ./futuriste.png

# Cas 2 : Image seule
curl -X POST http://localhost:3000/ \
  -F "image=@./source.png" \
  --output ./resultat.png
```

---

## 📁 Structure du projet

```
.
├── index.js                 # ✨ Point d'entrée universel Node.js (CLI + Serveur Express optionnel)
├── login.js                 # ✨ Raccourci de connexion Node.js
├── cli.py                   # ✨ Point d'entrée CLI Python
├── package.json             # ✨ Dépendances Node.js (Playwright, Express, Multer)
├── app/
│   ├── main.py              # FastAPI (inclus désormais POST / binaire)
│   ├── gemini_automation.py # Cœur d'automation Playwright (gestion des 3 cas & extraction d'images)
│   ├── browser_manager.py   # Gestionnaire de cycle de vie du navigateur persistant
│   ├── models.py            # Modèles Pydantic pour FastAPI
│   └── config.py            # Configuration et variables d'environnement
├── login_helper.py          # Assistant de connexion original Python
├── test_api.py              # Script de test de l'API
├── requirements.txt         # Dépendances Python
├── .env.example             # Modèle de variables d'environnement
├── LICENSE                  # Licence MIT d'origine
└── README.md                # Documentation complète
```

---

## ⚖️ Licence & Attribution

Ce projet conserve intégralement la licence **MIT** du projet source :
* Projet original : [`czarflix/GeminiCustomAPI`](https://github.com/czarflix/GeminiCustomAPI)
* Auteurs : Czarflix & contributeurs de Gemini Custom API
* Copyright (c) 2025 Gemini Custom API Contributors

*Avertissement : Cet outil automatise l'interface web de Google Gemini pour un usage personnel et expérimental. Il n'est pas affilié à Google.*
