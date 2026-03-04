# JWT 인증 · 프론트엔드 연동 (Next.js + Axios)

Access Token은 JSON 응답, Refresh Token은 HttpOnly 쿠키로 전달됩니다.  
401 + `code === "TOKEN_EXPIRED"` 시 `/v1/auth/refresh` 호출 후 재시도하는 Axios Interceptor 예시입니다.

---

## 1. 로그인

- **요청**: `POST /v1/auth/login` (email, password)
- **응답**: `data.data.accessToken` 저장 (예: 메모리/상태). Refresh Token은 쿠키로 설정되므로 별도 저장 불필요.
- **이후 요청**: `Authorization: Bearer <accessToken>` 헤더에 항상 포함.

```ts
// 로그인 후
const res = await axios.post('/v1/auth/login', { email, password }, { withCredentials: true });
const accessToken = res.data?.data?.accessToken;
// accessToken을 상태/메모리에 보관 (localStorage 사용 시 XSS 주의)
```

---

## 2. API 요청 시 Bearer 헤더

```ts
axios.defaults.withCredentials = true;

axios.interceptors.request.use((config) => {
  const token = getAccessToken(); // 상태/스토어에서 조회
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

---

## 3. 401 + TOKEN_EXPIRED 시 Refresh 후 재시도

Access Token 만료 시 서버는 `401`과 `detail.code === "TOKEN_EXPIRED"`를 반환합니다.  
이때 `/v1/auth/refresh`를 호출해 새 Access Token을 받은 뒤, 실패한 요청을 새 토큰으로 재시도합니다.

```ts
import axios, { AxiosError } from 'axios';

const REFRESH_URL = '/v1/auth/refresh';

axios.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const original = err.config as typeof err.config & { _retry?: boolean };

    if (err.response?.status !== 401 || original._retry) {
      return Promise.reject(err);
    }

    const code = (err.response?.data as { detail?: { code?: string } })?.detail?.code;
    if (code !== 'TOKEN_EXPIRED') {
      return Promise.reject(err);
    }

    original._retry = true;

    try {
      const refreshRes = await axios.post(REFRESH_URL, {}, { withCredentials: true });
      const newToken = refreshRes.data?.data?.accessToken;
      if (newToken) {
        setAccessToken(newToken); // 상태/스토어에 갱신
        if (original.headers) original.headers.Authorization = `Bearer ${newToken}`;
        return axios(original);
      }
    } catch (refreshErr) {
      // Refresh 실패 시 로그아웃 처리 등
    }
    return Promise.reject(err);
  }
);
```

- `withCredentials: true`: Refresh Token 쿠키가 서버로 전송되도록 필수.
- 동시에 여러 요청이 401을 받을 경우, Refresh를 한 번만 수행하고 나머지는 새 토큰으로 재시도하도록 큐/플래그 처리하면 좋습니다.

---

## 4. 로그아웃

- **요청**: `POST /v1/auth/logout` (withCredentials: true)
- **이후**: 저장한 Access Token 삭제, Refresh 쿠키는 서버에서 제거됨.

```ts
await axios.post('/v1/auth/logout', {}, { withCredentials: true });
clearAccessToken();
```

---

## 5. 요약

| 항목 | 내용 |
|------|------|
| Access Token | 응답 `data.data.accessToken` → 클라이언트가 저장 후 `Authorization: Bearer` 로 전송 |
| Refresh Token | HttpOnly 쿠키로 전달, 클라이언트는 저장 불필요 |
| 401 + TOKEN_EXPIRED | `/v1/auth/refresh` 호출 → 새 accessToken으로 실패 요청 재시도 |
| 로그아웃 | `POST /v1/auth/logout` 후 Access Token 삭제 |

상세 API 스펙은 `docs/api-codes.md` 및 Swagger/ReDoc을 참고하세요.
