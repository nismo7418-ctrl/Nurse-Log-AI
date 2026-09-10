# Déploiement NurseLog AI

## Environnement de développement

### Local (Streamlit)
```bash
streamlit run src/app.py
```

### Docker (dev)
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8501
CMD ["streamlit", "run", "src/app.py", "--server.headless=true"]
```

```bash
docker build -t nurselog-dev .
docker run -p 8501:8501 -e APP_LANG=fr nurselog-dev
```

## Environnement de production

### Infrastructure recommandée (Phase 3)

| Composant | Service | Coût estimé |
|-----------|---------|-------------|
| Compute | AWS ECS / GCP Cloud Run | €50/mois |
| Database | Supabase / AWS RDS | €25/mois |
| Storage | AWS S3 | €5/mois |
| CDN | CloudFlare | Gratuit |
| Monitoring | Grafana Cloud (free tier) | Gratuit |
| Domaine | nurse-log.be | €10/an |

**Total estimé** : ~€90/mois (couvert par abonnements dès 1er utilisateur)

### CI/CD (GitHub Actions)

```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/ -v
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: docker build -t nurselog .
      - run: docker push nurselog
```

### Variables d'environnement production

```yaml
APP_LANG: fr
DEBUG: false
LOG_LEVEL: WARNING
DATABASE_URL: postgresql://user:pass@host:5432/nurselog
OPENAI_API_KEY: ${VAULT_OPENAI_KEY}
JWT_SECRET_KEY: ${VAULT_JWT_SECRET}
CORS_ORIGINS: "https://nurse-log.be"
```

## Checklist conformité (Phase 3)

- [ ] Hébergement UE (Frankfurt/Amsterdam)
- [ ] Chiffrement AES-256 au repos
- [ ] TLS 1.3 en transit
- [ ] Politique de rétention données (3 ans min. Belgique)
- [ ] Droit à l'oubli (RGPD)
- [ ] Export données patient
- [ ] Logs d'audit
- [ ] Notification breach (< 72h RGPD)
- [ ] DPO désigné
- [ ] Analyse d'impact RGPD
- [ ] Certification HDS/HDC
- [ ] Assurance responsabilité civile professionnelle

## Backup & Recovery

### Stratégie backup
- **Base de données** : Snapshot quotidien + WAL continu
- **Fichiers** : Replication multi-AZ
- **RTO** : 4 heures
- **RPO** : 1 heure

### Plan de reprise
```bash
# Restauration base de données
pg_restore -d nurselog backup_$(date +%Y%m%d).sql

# Restauration fichiers
aws s3 sync s3://nurselog-backup/ /data/
```

## Monitoring & Alertes

### Métriques clés
- **Disponibilité** : > 99.9%
- **Latence API** : < 200ms (p95)
- **Erreurs** : < 0.1% des requêtes
- **Utilisation CPU** : < 70%
- **Utilisation RAM** : < 80%

### Alertes (Grafana/PagerDuty)
- CPU > 90% pendant 5min → Warning
- Erreur 5xx > 1% → Critical
- Disponibilité < 99% → Page immédiatement
- Disk > 85% → Warning
