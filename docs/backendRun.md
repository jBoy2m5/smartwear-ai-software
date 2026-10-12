cd C:\Task\smartwear-ai
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload

cd C:\Task\smartwear-ai
python -B .\ai\integration\run_connected.py


cd C:\Task\smartwear-ai\frontend
npm.cmd ci
npm.cmd run dev