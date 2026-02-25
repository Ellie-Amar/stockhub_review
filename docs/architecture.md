# Architecture StockHub

## Vue d'ensemble du système

StockHub est un système de gestion des stocks multi-canal construit avec Django et MongoDB. Il gère le suivi des stocks, la synchronisation avec les places de marché et le traitement des webhooks pour les opérations e-commerce.

---

## Architecture de haut niveau

```mermaid
flowchart TB
    subgraph External["Systèmes externes"]
        AMZ[API Amazon]
        CDI[API Cdiscount]
        WEB[Interface web]
    end

    subgraph Webhooks["Couche Webhook"]
        WH[Gestionnaires de webhooks]
    end

    subgraph Core["Services principaux"]
        INV[Service d'inventaire]
        SYNC[Service de synchronisation]
    end

    subgraph Data["Couche de données"]
        DB[(MongoDB)]
    end

    subgraph Background["Tâches en arrière-plan"]
        CEL[Workers Celery]
    end

    AMZ -->|Notifications de vente| WH
    CDI -->|Notifications de vente| WH
    WEB -->|Commandes| WH

    WH --> INV
    INV --> DB
    INV --> SYNC

    SYNC --> AMZ
    SYNC --> CDI
    SYNC --> WEB

    CEL -.->|Synchronisation planifiée| SYNC
```

---

## Description des composants

### 1. Couche Webhook (`src/webhooks/`)

**Objectif :** Recevoir les callbacks HTTP des places de marché lors de ventes, retours ou autres événements.

**Responsabilités :**
- Analyser les charges utiles des webhooks entrants
- Valider l'authenticité des requêtes
- Router les événements vers les gestionnaires appropriés
- Renvoyer un accusé de réception à la place de marché

**Points d'entrée :**
| Point d'entrée | Objectif |
|----------------|----------|
| `POST /webhooks/sale/` | Traiter les notifications de vente |
| `POST /webhooks/return/` | Traiter les notifications de retour |

---

### 2. Service d'inventaire (`src/inventory/`)

**Objectif :** Logique métier centrale pour la gestion des stocks.

**Responsabilités :**
- Enregistrer les mouvements de stock (ventes, retours, ajustements)
- Maintenir des comptages de stock précis
- Appliquer les règles métier (pas de stock négatif)
- Déclencher les alertes de réapprovisionnement
- Gérer les réservations par canal

**Opérations clés :**
```
record_movement(product, type, quantity, channel, reason)
    → Met à jour le stock
    → Enregistre le mouvement
    → Déclenche la synchronisation
    → Vérifie le seuil d'alerte

get_available_stock(product)
    → Stock physique - Réservé - En transit
```

---

### 3. Service de synchronisation (`src/sync/`)

**Objectif :** Propager les modifications de stock vers tous les canaux de vente.

**Responsabilités :**
- Construire les payloads API pour chaque place de marché
- Appeler les API des places de marché pour mettre à jour les annonces
- Gérer les erreurs API et les tentatives de réessai
- Suivre l'état de synchronisation

**Flux :**
```mermaid
sequenceDiagram
    participant INV as Service d'inventaire
    participant SYNC as Service de synchronisation
    participant AMZ as Amazon
    participant CDI as Cdiscount

    INV->>SYNC: sync_stock(product)
    SYNC->>AMZ: PUT /inventory/{sku}
    AMZ-->>SYNC: 200 OK
    SYNC->>CDI: PUT /stock/{sku}
    CDI-->>SYNC: 200 OK
    SYNC-->>INV: Synchronisation terminée
```

---

### 4. Modèles de données (`src/inventory/models.py`)

```mermaid
erDiagram
    Product ||--o{ StockMovement : "possède"
    Product ||--o{ StockReservation : "possède"
    Channel ||--o{ StockMovement : "source"
    Channel ||--o{ StockReservation : "réservé pour"

    Product {
        uuid id PK
        string sku
        string name
        int physical_stock
        int alert_threshold
        datetime created_at
        datetime updated_at
    }

    Channel {
        uuid id PK
        string name
        string api_key
        string api_url
        bool is_active
    }

    StockReservation {
        uuid id PK
        uuid product_id FK
        uuid channel_id FK
        int quantity
        datetime created_at
    }

    StockMovement {
        uuid id PK
        uuid product_id FK
        string movement_type
        int quantity
        uuid channel_id FK
        string reason
        datetime created_at
    }
```

---

## Exemples de flux de données

### Flux de traitement des ventes

```mermaid
sequenceDiagram
    participant MKT as Place de marché
    participant WH as Gestionnaire de webhook
    participant INV as Service d'inventaire
    participant SYNC as Service de synchronisation
    participant DB as MongoDB

    MKT->>WH: POST /webhooks/sale/
    WH->>INV: record_sale(sku, qty, channel)
    INV->>DB: Créer StockMovement
    INV->>DB: Mettre à jour Product.physical_stock
    INV->>SYNC: sync_stock(product)
    SYNC->>MKT: Mettre à jour tous les canaux
    SYNC-->>INV: Synchronisation terminée
    INV-->>WH: Succès
    WH-->>MKT: 200 OK
```

### Flux de traitement des retours

```mermaid
sequenceDiagram
    participant WH as Entrepôt
    participant INV as Service d'inventaire
    participant SYNC as Service de synchronisation
    participant DB as MongoDB

    WH->>INV: record_return(sku, qty, reason)
    INV->>DB: Créer StockMovement (RETOUR)
    INV->>DB: Mettre à jour Product.physical_stock
    INV->>SYNC: sync_stock(product)
    SYNC-->>INV: Synchronisation terminée
```

---

## Stack technologique

| Composant | Technologie |
|-----------|-------------|
| Framework web | Django 4.2 |
| Couche API | Django REST Framework |
| Base de données | MongoDB via djongo |
| File de tâches | Celery avec Redis |
| Client HTTP | requests |

---

## Configuration

L'application est configurée via `src/settings.py` :

- **Base de données :** Chaîne de connexion MongoDB
- **Identifiants des places de marché :** Clés API et URLs pour chaque canal
- **Celery :** URL du broker et paramètres des tâches
- **Journalisation :** Configuration des logs applicatifs

---

## Considérations de déploiement

1. **Mise à l'échelle :** Les gestionnaires de webhooks doivent être horizontalement scalables
2. **Fiabilité :** Les workers Celery nécessitent une surveillance des tâches bloquées
3. **Observabilité :** Les mouvements de stock doivent être journalisés pour audit
4. **Secrets :** Les clés API des places de marché doivent être stockées de manière sécurisée