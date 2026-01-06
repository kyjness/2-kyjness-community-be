from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "hello"}

# POST 엔드포인트 추가
@app.post("/echo")
def echo(data: dict):
    return {
        "received": data,
        "status": "ok"
    }