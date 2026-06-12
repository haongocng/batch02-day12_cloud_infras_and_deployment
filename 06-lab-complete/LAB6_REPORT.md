# Lab 6 Report - Productionize Day08 DrugLaw RAG Agent

## 1. Project được chọn

Trong Lab 6, project mặc định trong `06-lab-complete` đã được thay bằng project từ buổi trước:

- Project gốc: `Day08_RAG_pipeline_cohort2`
- Loại project: RAG Agent hỏi đáp về luật và tin tức liên quan đến ma túy
- Mục tiêu: đưa project RAG từ môi trường notebook/local sang dạng API production-ready có thể deploy public

Project sau khi restructure nằm trong:

```text
06-lab-complete/
```

## 2. Cấu trúc sau khi productionization

Các thành phần chính:

```text
06-lab-complete/
├── app/
│   ├── main.py          # FastAPI production wrapper
│   └── config.py        # 12-Factor config từ environment variables
├── src/                 # RAG pipeline từ Day08
├── data/index/          # Local RAG index dùng khi deploy
├── evaluation/          # Evaluation artifacts từ Day08
├── Dockerfile           # Multi-stage Docker build
├── docker-compose.yml   # Local stack với Redis
├── railway.toml         # Railway deployment config
├── requirements.txt     # Runtime dependencies nhẹ cho production
├── requirements-full.txt# Optional dependencies cho ingestion/UI/evaluation
└── check_production_ready.py
```

## 3. Các bước productionization đã áp dụng

### 3.1. API hóa project

Project Day08 ban đầu được đưa vào FastAPI backend với các endpoint:

- `GET /` - thông tin service
- `GET /health` - liveness health check
- `GET /ready` - readiness check, kiểm tra RAG index
- `POST /ask` - endpoint hỏi đáp RAG
- `GET /metrics` - metric cơ bản về request, error, cost
- `GET /docs` - Swagger UI để test API

Endpoint chính:

```text
POST /ask
```

Input mẫu:

```json
{
  "question": "Hình phạt cho tội tàng trữ trái phép chất ma túy theo Điều 249 là gì?",
  "top_k": 5,
  "use_reranking": true
}
```

### 3.2. Environment variables

Các secret/config không hardcode trong code, mà lấy từ environment variables:

- `AGENT_API_KEY`
- `JWT_SECRET`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `OPENROUTER_MODEL`
- `JINA_API_KEY`
- `COHERE_API_KEY`
- `WEAVIATE_URL`
- `WEAVIATE_API_KEY`
- `PAGEINDEX_API_KEY`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

Các file `.env` và `.env.local` chỉ dùng local, không commit secret lên GitHub.

### 3.3. Authentication

API `/ask` và `/metrics` được bảo vệ bằng header:

```text
X-API-Key: <AGENT_API_KEY>
```

OpenRouter/MiniMax key không được dùng trực tiếp ở client. Server tự đọc key từ environment để gọi LLM provider.

### 3.4. Rate limiting và cost guard

Backend có logic:

- Giới hạn số request/phút theo `RATE_LIMIT_PER_MINUTE`
- Ước lượng chi phí request dựa trên input/output tokens
- Chặn request nếu vượt `DAILY_BUDGET_USD`

Mục tiêu là tránh public endpoint bị gọi quá nhiều gây tốn chi phí API.

### 3.5. Health check và readiness check

Health check:

```text
GET /health
```

Kiểm tra:

- App còn sống
- Version/environment
- RAG index có tồn tại không
- LLM provider đã cấu hình chưa
- Jina/Cohere/Weaviate/PageIndex có được cấu hình không

Readiness check:

```text
GET /ready
```

Kiểm tra service đã sẵn sàng nhận traffic và có RAG index tại:

```text
/app/data/index/chunks.json
```

### 3.6. Dockerization

Đã dùng Dockerfile multi-stage:

- Stage `builder`: cài dependencies
- Stage `runtime`: copy app, src, data index và chạy bằng non-root user

Một số điểm production:

- Base image: `python:3.11-slim`
- Non-root user: `agent`
- Có `HEALTHCHECK`
- Không copy `.env` vào image
- Runtime dependencies được tối ưu để không kéo `torch`/`cudnn`

`requirements.txt` chỉ giữ dependency cần cho API runtime. Các thư viện nặng như Streamlit, sentence-transformers, deepeval, crawl4ai được chuyển sang `requirements-full.txt` để dùng khi cần offline ingestion/evaluation.

### 3.7. Railway deployment

Đã cấu hình Railway bằng:

```text
06-lab-complete/railway.toml
```

Các setting chính:

- Root Directory: `/06-lab-complete`
- Builder: Dockerfile
- Start command: chạy FastAPI bằng Uvicorn
- Healthcheck path: `/health`
- Public networking: port `8000`

## 4. Public API URL

API đã deploy public trên Railway:

```text
https://day12-production-7973.up.railway.app
```

Swagger UI:

```text
https://day12-production-7973.up.railway.app/docs
```

Health check:

```text
https://day12-production-7973.up.railway.app/health
```

Ask endpoint:

```text
https://day12-production-7973.up.railway.app/ask
```

## 5. Cách test API

### 5.1. Health check

```powershell
curl.exe https://day12-production-7973.up.railway.app/health
```

### 5.2. Readiness check

```powershell
curl.exe https://day12-production-7973.up.railway.app/ready
```

### 5.3. Gọi RAG endpoint

```powershell
Invoke-RestMethod -Uri "https://day12-production-7973.up.railway.app/ask" `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-API-Key"="<AGENT_API_KEY>"} `
  -Body '{"question":"Hình phạt cho tội tàng trữ trái phép chất ma túy theo Điều 249 là gì?","top_k":5,"use_reranking":true}'
```

## 6. CI/CD

Đã chuẩn bị GitHub Actions workflow local tại:

```text
.github/workflows/day12-ci.yml
```

Workflow dự kiến chạy khi push/PR:

- Checkout code
- Setup Python 3.11
- Install runtime dependencies
- Compile `app` và `src`
- Run production readiness checker
- Build Docker image

Lưu ý: để push file workflow lên GitHub cần token có quyền `workflow`. Nếu token hiện tại chưa có quyền này, có thể thêm workflow trực tiếp qua GitHub UI hoặc cập nhật Personal Access Token.

## 7. Kết quả hoàn thành checklist

- [x] Replace project trong `06-lab-complete` bằng project từ buổi trước
- [x] Restructure thành FastAPI production API
- [x] Sử dụng environment variables, không hardcode secrets
- [x] Có authentication bằng API key
- [x] Có rate limiting và cost guard
- [x] Có `/health` và `/ready`
- [x] Có Dockerfile production
- [x] Có Docker Compose local
- [x] Có Railway deployment config
- [x] Deploy public thành công trên Railway
- [x] Ghi lại public API URL

## 8. Ghi chú

Hiện tại service deploy là backend API, không phải Streamlit UI. Có thể test qua Swagger UI tại `/docs`. Nếu cần giao diện người dùng, có thể bổ sung một trang `/ui` nhẹ trong FastAPI hoặc deploy Streamlit thành một Railway service riêng gọi vào FastAPI backend.
