# TradingProject

Python paper-trading project. Order submission is disabled by default.

## Setup

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env   # then fill in your paper-trading keys
```

## Safety

- `trading/safety.py` blocks order submission unless `TRADING_MODE=paper`
  and `ORDER_SUBMISSION_ENABLED=true`. Both default to the safe values.
- `.env`, key files, and generated data (`data/`, `logs/`, `*.csv`, `*.db`, ...)
  are git-ignored. See `.gitignore`.
