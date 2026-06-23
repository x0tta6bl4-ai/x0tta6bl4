from fastapi import FastAPI
import uvicorn
from src.api.vpn import router as vpn_router
from src.api.billing_api import router as billing_router
from database import init_database

app = FastAPI(title="x0tta6bl4 MaaS Backend")
app.include_router(vpn_router)
app.include_router(billing_router)

if __name__ == "__main__":
    init_database()
    uvicorn.run(app, host="127.0.0.1", port=8001)
