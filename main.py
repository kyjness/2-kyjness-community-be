# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth_route, posts_route
# from app.routes import users_route, comments_route, likes_route  # 아직 안 만든 것들

app = FastAPI(
    title="PuppyTalk API",
    description="커뮤니티 백엔드 API",
    version="1.0.0"
)

# CORS 설정 (프론트엔드와 연결할 때 필요)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 "*", 배포 시에는 구체적인 도메인으로 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
#app.include_router(auth_route.router)
app.include_router(posts_route.router)
# app.include_router(users_route.router)
# app.include_router(comments_route.router)
# app.include_router(likes_route.router)

# 루트 엔드포인트 (서버 작동 확인용)
@app.get("/")
def root():
    return {
        "message": "PuppyTalk API is running!",
        "version": "1.0.0",
        "docs": "/docs"
    }

# 헬스체크 엔드포인트 (서버 상태 확인용)
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# 서버 실행 (개발용)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

