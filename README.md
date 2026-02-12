# Filtre d'emails pour OVH

Ce projet contient des scripts Python pour filtrer automatiquement les emails d'une boîte mail OVH, en remplacement des scripts Sieve non disponibles sur le serveur de mail.

## Fonctionnalités

- **Filtrage intelligent** des emails en fonction de :
  - Liste noire (blacklist) des expéditeurs
  - Liste blanche (whitelist) des expéditeurs
  - Indicateurs de spam (mots-clés, scores OVH/SpamAssassin)
  - Détection des newsletters
  - Vérification des adresses destinataires valides

- **Organisation automatique** des emails dans différents dossiers :
  - **Junk** pour les spams
  - **Newsletters** pour les newsletters
  - **Archive** pour les emails spécifiques (comme ceux de Brevo)

- **Gestion des listes** :
  - Ajout automatique à la  liste noire de tous les expéditeurs des emails qui sont ganés dans le dossier Blacklist
  - Configuration via fichiers texte des autres listes

## Configuration

1. **Fichiers de configuration** :
   - `constants.py` : Paramètres de connexion et dossiers
   - `config/spam_keywords.txt` : Mots-clés de spam
   - `config/blacklist.txt` : Liste noire
   - `config/whitelist_from.txt` : Liste blanche des expéditeurs
   - `config/whitelist_to_cc.txt` : Liste blanche des destinataires

2. **Prérequis** :
   - Python 3.x
   - Modules Python standard (imaplib, email, argparse)

## Utilisation

### Installation

1. Clonez ce dépôt :
   ```bash
   git clone https://github.com/votre-utilisateur/email-filter.git
   cd email-filter
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

### Exécution

```bash
# Filtrer tous les emails (mode interactif: validder cahque décision un mail après l'autres, ou whitelist si besoin)
./junk.sh

# Filtrer les 50 derniers emails (mode automatique)
./junk.sh -l 50 -y

# Filtrer un email spécifique par ID OVH
./junk.sh -e "votre-id-ovh"
```

### Options

| Option | Description |
|--------|-------------|
| `-l N` ou `--last-emails N` | Filtrer les N derniers emails |
| `-y` ou `--yes-to-all`| Mode automatique (sans confirmation) |
| `-e ID` ou `--email-id ID` | Filtrer un email spécifique par ID OVH |

## Fonctionnement

1. Le script se connecte au serveur IMAP OVH
2. Il parcourt les emails selon le mode sélectionné
3. Pour chaque email, il vérifie :
   - Si l'expéditeur est dans la liste noire
   - Si l'expéditeur est dans la liste blanche
   - Si l'email contient des indicateurs de spam
   - Si les destinataires sont valides
4. Selon les résultats, l'email est déplacé vers :
   - Le dossier Junk (spam)
   - Le dossier Newsletters
   - Le dossier Archive
   - Ou laissé dans la boîte de réception
   
## Licence

[MIT](LICENSE)
