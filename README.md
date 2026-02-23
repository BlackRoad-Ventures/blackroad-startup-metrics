# blackroad-startup-metrics

![CI](https://github.com/BlackRoad-Ventures/blackroad-startup-metrics/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Startup KPI and metrics tracking for the BlackRoad OS platform.

## Features
- MRR/ARR calculation from customer data
- Churn rate tracking
- Runway calculation with burn rate
- Headcount and salary tracking
- Funding round management
- KPI dashboard

## Usage
```bash
python main.py create "My Startup" --stage seed
python main.py add-customer <id> "Acme Corp" 500
python main.py fund <id> "Seed" 500000
python main.py dashboard <id> --burn 50000
python main.py mrr <id>
python main.py runway <id> 50000
```
