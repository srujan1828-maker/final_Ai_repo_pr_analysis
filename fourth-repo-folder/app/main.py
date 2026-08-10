from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from app.sandbox import manager
from app.models import CodeRequest, TestRequest

app = FastAPI(
    title="Sandbox Runtime Service",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "service": "Sandbox Runtime",
        "status": "running"
    }


@app.post("/sandbox")
async def create_sandbox():
    sandbox = await manager.create()

    return {
        "status": "Sandbox Created",
        "sandbox_id": str(sandbox)
    }


@app.post("/run")
async def run(request: CodeRequest):
    sandbox = await manager.create()

    try:
        result = await manager.run_code(
            sandbox=sandbox,
            code=request.code,
            packages=request.packages
        )
        return result

    finally:
        await manager.cleanup()


@app.post("/test")
async def test(request: TestRequest):
    sandbox = await manager.create()

    try:
        result = await manager.run_tests(
            sandbox=sandbox,
            code=request.code,
            tests=request.tests,
            packages=request.packages
        )
        return result

    finally:
        await manager.cleanup()