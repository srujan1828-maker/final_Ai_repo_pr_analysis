from pydantic import BaseModel


class CodeRequest(BaseModel):
    code: str
    packages: list[str] = []


class TestRequest(BaseModel):
    code: str
    tests: str
    packages: list[str] = []