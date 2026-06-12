# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Mục tiêu của Part 1

Part 1 giúp phân biệt giữa một ứng dụng "chạy được trên máy local" và một ứng dụng đủ tốt để deploy lên môi trường production/cloud.

Vấn đề chính được quan sát là: code có thể chạy bình thường trên laptop, nhưng vẫn có thể fail khi deploy vì hardcoded secrets, config không linh hoạt, khác biệt environment, thiếu health check, thiếu logging chuẩn và không xử lý shutdown đúng cách.

---

### Exercise 1.1: Anti-patterns found

Sau khi đọc file `01-localhost-vs-production/develop/app.py`, tôi tìm thấy các vấn đề sau:

1. **Hardcoded API key trong code**

   Code khai báo trực tiếp:

   ```python
   OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"
   ```

   Đây là anti-pattern nghiêm trọng vì nếu push code lên GitHub public, secret có thể bị lộ ngay lập tức.

2. **Hardcoded database URL có username/password**

   Code chứa trực tiếp thông tin database:

   ```python
   DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"
   ```

   Database credential không nên nằm trong source code. Production app nên đọc các giá trị này từ environment variables hoặc secret manager.

3. **Debug mode bị bật cứng**

   Code khai báo:

   ```python
   DEBUG = True
   ```

   Debug mode phù hợp cho development nhưng không phù hợp cho production vì có thể lộ thông tin nội bộ, stack trace hoặc tạo hành vi không ổn định.

4. **Không có config management**

   Các giá trị như API key, database URL, debug mode, max tokens, host và port đều nằm trực tiếp trong code. Điều này khiến app khó chuyển đổi giữa local, staging và production.

5. **Dùng `print()` thay vì structured logging**

   Trong endpoint `/ask`, app dùng:

   ```python
   print(f"[DEBUG] Got question: {question}")
   print(f"[DEBUG] Response: {response}")
   ```

   Production app nên dùng logging chuẩn, tốt nhất là structured JSON logging để dễ đọc, tìm kiếm và phân tích trên cloud logging platform.

6. **Log ra secret**

   Code có dòng:

   ```python
   print(f"[DEBUG] Using key: {OPENAI_API_KEY}")
   ```

   Đây là lỗi bảo mật vì API key có thể xuất hiện trong terminal, log file hoặc cloud log.

7. **Không có health check endpoint**

   Bản develop không có endpoint như `GET /health`. Khi deploy cloud, platform không có cách đơn giản để biết app còn sống hay cần restart.

8. **Host bị cố định là `localhost`**

   Code chạy uvicorn với:

   ```python
   host="localhost"
   ```

   Khi chạy trong Docker/container hoặc cloud, app thường cần bind vào `0.0.0.0` để nhận traffic từ bên ngoài container.

9. **Port bị hardcode là `8000`**

   Code chạy với:

   ```python
   port=8000
   ```

   Trên các platform như Railway hoặc Render, port thường được inject qua biến môi trường `PORT`. Nếu app không đọc `PORT`, deploy có thể fail.

10. **Bật `reload=True` trong code chạy app**

    Code dùng:

    ```python
    reload=True
    ```

    Auto reload chỉ phù hợp trong development. Production không nên bật reload vì có thể gây restart không cần thiết và không ổn định.

11. **Không xử lý graceful shutdown**

    Bản develop không có xử lý `SIGTERM` hoặc lifecycle shutdown. Khi cloud platform stop/restart container, request đang chạy có thể bị ngắt đột ngột.

---

### Exercise 1.2: Run basic version

Tôi đã chạy basic/develop version bằng các lệnh:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment\01-localhost-vs-production\develop
pip install -r requirements.txt
python app.py
```

Sau đó test endpoint `/ask`:

```powershell
curl.exe -X POST "http://localhost:8000/ask?question=hello"
```

Kết quả:

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Nhận xét:

- App chạy được trên local.
- Endpoint `/ask` trả response thành công.
- Tuy nhiên app chưa production-ready vì vẫn có hardcoded secrets, hardcoded port, debug/reload mode, thiếu health check, thiếu readiness check, thiếu structured logging và thiếu graceful shutdown.

Kết luận: "It works on my machine" không đồng nghĩa với "ready for production".

---

### Exercise 1.3: Compare with advanced/production version

Tôi đã chuyển sang bản production:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment\01-localhost-vs-production\production
Copy-Item .env.example .env
pip install -r requirements.txt
python app.py
```

Test health check:

```powershell
curl.exe http://localhost:8000/health
```

Kết quả:

```json
{"status":"ok","uptime_seconds":17.1,"version":"1.0.0","environment":"development","timestamp":"2026-06-12T07:33:38.920099+00:00"}
```

Test readiness check:

```powershell
curl.exe http://localhost:8000/ready
```

Kết quả:

```json
{"ready":true}
```

Khi test endpoint `/ask`, tôi đã chạy:

```powershell
curl.exe -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\":\"hello\"}"
```

Kết quả gặp lỗi:

```text
Internal Server Error
curl: (3) URL rejected: Port number was not a decimal number between 0 and 65535
```

Nhận xét về lỗi này:

- `/health` và `/ready` đều hoạt động, nên app production đã start thành công.
- Lỗi `curl: (3) URL rejected` thường xảy ra do cách escape JSON trong PowerShell làm curl hiểu sai một phần chuỗi request.
- Đây nhiều khả năng là lỗi cú pháp lệnh curl/quoting trên PowerShell, không phải bằng chứng rằng app production bị sai thiết kế.

Lệnh nên dùng trong PowerShell là:

```powershell
curl.exe -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{\"question\":\"hello\"}'
```

Hoặc dùng JSON bằng single quote đơn giản hơn:

```powershell
curl.exe -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question":"hello"}'
```

Nếu vẫn gặp lỗi parse body trên PowerShell, có thể dùng `Invoke-RestMethod`:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -ContentType "application/json" -Body '{"question":"hello"}'
```

---

### Comparison table

| Feature | Basic / Develop | Advanced / Production | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode trực tiếp trong `app.py` | Đọc từ environment variables qua `config.py` | Giúp app dễ chạy ở nhiều môi trường khác nhau mà không cần sửa code |
| Secrets | API key và database URL nằm trong source code | Secret lấy từ env như `OPENAI_API_KEY`, `AGENT_API_KEY` | Tránh lộ secret khi push code hoặc share repo |
| Port | Cố định `8000` | Đọc từ `PORT` env var | Cloud platform thường cấp port động qua env |
| Host | Cố định `localhost` | Dùng `0.0.0.0` qua `HOST` env var | Container/cloud cần nhận traffic từ bên ngoài process/container |
| Debug mode | `DEBUG = True`, `reload=True` | Debug/reload phụ thuộc env `DEBUG` | Production không nên bật debug hoặc auto reload |
| Health check | Không có `/health` | Có `GET /health` | Platform/monitoring biết app còn sống hay cần restart |
| Readiness check | Không có `/ready` | Có `GET /ready` | Load balancer chỉ route traffic khi app đã sẵn sàng |
| Logging | Dùng `print()` | Dùng structured JSON logging | Log production dễ parse, search và monitor hơn |
| Secret logging | Có log API key ra console | Không log secret | Giảm rủi ro lộ credential trong logs |
| Input validation | Nhận `question` qua query param đơn giản | Đọc JSON body và trả `422` nếu thiếu `question` | API rõ ràng hơn, lỗi dễ debug hơn |
| Shutdown | Không xử lý shutdown | Có lifespan và `SIGTERM` handler | Khi deploy/restart container, app có cơ hội cleanup và hoàn thành request đang chạy |
| Cloud readiness | Chạy được trên local nhưng khó deploy | Có host/port/env/health/readiness phù hợp cloud | Giảm lỗi "works on my machine" khi đưa lên Railway/Render/Docker |

---

### Discussion questions

#### 1. Điều gì xảy ra nếu push code có API key hardcode lên GitHub public?

API key có thể bị crawler hoặc người khác phát hiện. Khi đó họ có thể dùng key để gọi dịch vụ, gây mất tiền, lộ dữ liệu hoặc làm vượt quota. Nếu chuyện này xảy ra, cần revoke key cũ, tạo key mới, kiểm tra logs và xóa secret khỏi git history nếu cần.

#### 2. Tại sao stateless quan trọng khi scale?

Khi scale nhiều instance, mỗi instance có memory riêng. Nếu lưu state trong memory local, request tiếp theo có thể đi vào instance khác và mất context. Stateless design giúp app scale ngang tốt hơn vì state được đưa ra ngoài app, ví dụ Redis hoặc database.

#### 3. 12-Factor nói "dev/prod parity" nghĩa là gì trong thực tế?

Dev/prod parity nghĩa là môi trường development và production nên giống nhau nhất có thể: cùng version Python, dependency, cách config qua env, cách chạy app, cách logging và cách deploy. Mục tiêu là giảm lỗi chỉ xuất hiện khi deploy.

---

### Checkpoint 1

- [x] Hiểu tại sao hardcode secrets là nguy hiểm.
- [x] Biết cách dùng environment variables thông qua `production/config.py` và `.env.example`.
- [x] Hiểu vai trò của health check endpoint qua `/health`.
- [x] Hiểu readiness check qua `/ready`.
- [x] Biết graceful shutdown là gì và vì sao cần xử lý `SIGTERM`.

### Kết luận Part 1

Bản `develop` chứng minh rằng một app có thể chạy được trên local nhưng vẫn chưa đủ điều kiện production. Bản `production` cải thiện bằng cách áp dụng các nguyên tắc 12-Factor: config từ env, không hardcode secret, structured logging, health/readiness endpoint, bind host phù hợp cloud, port linh hoạt và graceful shutdown.

---

## Part 2: Docker Containerization

### Mục tiêu của Part 2

Part 2 giải quyết vấn đề "works on my machine" ở mức environment và dependency. Thay vì phụ thuộc vào Python version, OS, package đã cài trên máy cá nhân, Docker đóng gói app cùng dependencies vào một image để có thể chạy nhất quán trên nhiều môi trường khác nhau.

Docker giúp:

- Đảm bảo môi trường chạy nhất quán.
- Dễ deploy hơn vì app được đóng gói thành image.
- Cô lập dependency giữa các project.
- Build và chạy lại được theo cách reproducible.

---

### Exercise 2.1: Dockerfile questions

Sau khi đọc `02-docker/develop/Dockerfile`, tôi trả lời các câu hỏi như sau:

#### 1. Base image là gì?

Base image của bản develop là:

```dockerfile
FROM python:3.11
```

Đây là image Python đầy đủ, có sẵn runtime Python 3.11. Vì là bản full nên image khá lớn, phù hợp để học và debug nhưng chưa tối ưu cho production.

#### 2. Working directory là gì?

Working directory trong container là:

```dockerfile
WORKDIR /app
```

Điều này nghĩa là các lệnh sau đó như `COPY`, `RUN`, `CMD` sẽ chạy trong thư mục `/app` bên trong container.

#### 3. Tại sao `COPY requirements.txt` trước?

Dockerfile copy `requirements.txt` trước khi copy source code:

```dockerfile
COPY 02-docker/develop/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

Lý do là để tận dụng Docker layer cache. Dependency thường ít thay đổi hơn source code. Nếu chỉ sửa `app.py`, Docker có thể reuse layer đã cài dependencies, giúp build nhanh hơn. Nếu copy toàn bộ source trước rồi mới `pip install`, mỗi lần sửa code nhỏ cũng có thể làm Docker cài lại dependencies từ đầu.

#### 4. `CMD` vs `ENTRYPOINT` khác nhau thế nào?

- `CMD` là command mặc định khi container start. Người dùng có thể override dễ dàng khi chạy `docker run`.
- `ENTRYPOINT` định nghĩa executable chính của container. Nó cố định hơn và thường dùng khi container luôn phải chạy một chương trình chính.

Trong Dockerfile develop, app dùng:

```dockerfile
CMD ["python", "app.py"]
```

Điều này phù hợp cho lab vì đơn giản và dễ override khi cần debug.

---

### Exercise 2.2: Build and run develop image

Tôi đã build image develop từ root project:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
```

Sau đó kiểm tra image size:

```powershell
docker images my-agent:develop
```

Kết quả:

```text
IMAGE              ID             DISK USAGE   CONTENT SIZE
my-agent:develop   cb04e7a3499e       1.66GB          424MB
```

Tôi đã chạy container:

```powershell
docker run -p 8000:8000 my-agent:develop
```

Log container:

```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.17.0.1:60040 - "GET /health HTTP/1.1" 200 OK
```

Test health endpoint:

```powershell
curl.exe http://localhost:8000/health
```

Kết quả:

```json
{"status":"ok","uptime_seconds":11.9,"container":true}
```

Nhận xét:

- Image develop chạy thành công.
- App trong container expose được API qua port mapping `8000:8000`.
- Health check trả về `200 OK`.
- Tuy nhiên image develop khá lớn vì dùng `python:3.11` full image và single-stage build.

---

### Exercise 2.3: Multi-stage build

Sau khi đọc `02-docker/production/Dockerfile`, tôi thấy production Dockerfile dùng multi-stage build gồm 2 stage chính:

#### Stage 1: `builder`

```dockerfile
FROM python:3.11-slim AS builder
```

Stage này dùng để cài build dependencies và Python packages. Nó có thể chứa các tool như `gcc`, `libpq-dev`, `pip` và các dependency phục vụ quá trình build.

Vai trò của stage này:

- Cài system packages cần cho build.
- Cài Python dependencies từ `requirements.txt`.
- Chuẩn bị thư mục package để copy sang runtime stage.

#### Stage 2: `runtime`

```dockerfile
FROM python:3.11-slim AS runtime
```

Stage này là image cuối cùng dùng để chạy app. Nó chỉ copy những thứ cần thiết từ builder, ví dụ installed packages và source code.

Vai trò của stage này:

- Chạy app bằng runtime gọn hơn.
- Không giữ lại build tools không cần thiết.
- Chạy bằng non-root user `appuser` để an toàn hơn.
- Có `HEALTHCHECK`.
- Start app bằng `uvicorn`.

#### Lỗi đã gặp khi build production image

Ban đầu tôi chạy build từ folder:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment\02-docker\production
docker build -t my-agent:advanced .
```

Lệnh này bị lỗi vì Dockerfile có các dòng:

```dockerfile
COPY 02-docker/production/main.py .
COPY utils/mock_llm.py /app/utils/mock_llm.py
```

Nghĩa là Dockerfile mong build context là root project, không phải folder `02-docker/production`.

Lệnh đúng là:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
```

Ngoài ra, folder `02-docker/production` bị thiếu `requirements.txt` trong khi Dockerfile có dòng:

```dockerfile
COPY 02-docker/production/requirements.txt .
```

Tôi đã bổ sung file:

```text
02-docker/production/requirements.txt
```

với nội dung:

```text
fastapi==0.115.0
uvicorn[standard]==0.30.0
```

Sau khi sửa, production image build thành công.

#### Image size comparison

Kết quả image size:

```text
my-agent:develop    1.66GB disk usage, 424MB content size
my-agent:advanced   56.6MB
```

So sánh:

| Image | Build style | Size | Nhận xét |
|---|---|---:|---|
| `my-agent:develop` | Single-stage, `python:3.11` full | 1.66GB disk usage / 424MB content size | Dễ hiểu, dễ debug nhưng lớn |
| `my-agent:advanced` | Multi-stage, `python:3.11-slim` | 56.6MB | Nhỏ hơn nhiều, phù hợp production hơn |

Nếu so theo disk usage, image advanced nhỏ hơn khoảng:

```text
1.66GB -> 56.6MB, giảm khoảng 96.6%
```

Nếu so theo content size:

```text
424MB -> 56.6MB, giảm khoảng 86.7%
```

#### Tại sao image production nhỏ hơn?

Image production nhỏ hơn vì:

1. Dùng `python:3.11-slim` thay vì `python:3.11` full.
2. Dùng multi-stage build để tách build environment và runtime environment.
3. Runtime image không giữ lại build tools như compiler hoặc package build dependencies.
4. Chỉ copy dependencies và source code cần thiết để chạy app.
5. Dùng `--no-cache-dir` khi cài pip packages để không giữ pip cache.

#### Docker image nhỏ hơn có lợi gì?

Image nhỏ hơn có nhiều lợi ích quan trọng trong production:

1. **Pull image nhanh hơn**

   Khi deploy lên server/cloud, platform cần pull image trước khi chạy container. Image càng lớn thì thời gian pull càng lâu.

2. **Startup/deploy nhanh hơn**

   Image quá lớn làm quá trình deploy, restart hoặc scale instance mất nhiều thời gian hơn. Nếu app cần scale nhanh khi traffic tăng, image lớn sẽ làm phản ứng chậm.

3. **Cải thiện trải nghiệm người dùng**

   Nếu container khởi động chậm, request đầu tiên của user có thể phải chờ lâu hơn. Với AI agent, người dùng hỏi câu hỏi nhưng app chưa sẵn sàng thì phản hồi sẽ chậm, ảnh hưởng trực tiếp tới UX.

4. **Tiết kiệm bandwidth và storage**

   Image nhỏ hơn giúp giảm dung lượng lưu trữ trên registry, máy deploy và CI/CD cache.

5. **Giảm attack surface**

   Runtime image nhỏ thường chứa ít tool/package không cần thiết hơn, từ đó giảm bề mặt tấn công và rủi ro bảo mật.

6. **CI/CD nhanh hơn**

   Build, push, pull image nhanh hơn giúp vòng lặp phát triển và deploy ngắn hơn.

---

### Test production image

Tôi đã chạy production image ở port `8001` để tránh đụng port `8000`:

```powershell
docker run -d --name my-agent-advanced-test -p 8001:8000 my-agent:advanced
```

Test health:

```powershell
curl.exe http://localhost:8001/health
```

Kết quả:

```json
{"status":"ok","uptime_seconds":12.4,"version":"2.0.0","timestamp":"2026-06-12T08:04:58.975357"}
```

Khi test `/ask` bằng `curl.exe` trong PowerShell, có thể gặp lỗi `Internal Server Error` do JSON quoting không đúng. Log container cho thấy lỗi:

```text
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
```

Sau đó tôi test lại bằng `Invoke-RestMethod`:

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/ask" -Method Post -ContentType "application/json" -Body '{"question":"What is Docker?"}'
```

Kết quả trả về:

```text
Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!
```

Nhận xét:

- Production image chạy được.
- `/health` hoạt động.
- `/ask` hoạt động khi request body là JSON hợp lệ.
- Lỗi trước đó là lỗi shell quoting khi dùng curl trong PowerShell, không phải lỗi Docker image.

Sau khi test, tôi dừng container:

```powershell
docker stop my-agent-advanced-test
```

---

### Exercise 2.4: Docker Compose stack

Sau khi đọc `02-docker/production/docker-compose.yml`, stack gồm các service:

1. **agent**

   FastAPI AI agent. Service này build từ production Dockerfile và chạy app ở port internal `8000`.

2. **redis**

   Redis cache, dùng cho concept session cache/rate limiting.

3. **qdrant**

   Vector database, dùng cho concept RAG/vector search.

4. **nginx**

   Reverse proxy/load balancer. Client không gọi trực tiếp agent mà gọi Nginx qua port `80`.

Tôi đã sửa `docker-compose.yml` để build context đúng từ root project:

```yaml
build:
  context: ../..
  dockerfile: 02-docker/production/Dockerfile
  target: runtime
```

Tôi cũng tạo file local-only:

```text
02-docker/production/.env.local
```

File này đã được `.gitignore` ignore, dùng để Docker Compose đọc env mà không commit secret.

Validate compose config:

```powershell
docker compose -f 02-docker/production/docker-compose.yml config
```

Kết quả config hợp lệ. Docker Compose có cảnh báo:

```text
the attribute `version` is obsolete
```

Cảnh báo này không nghiêm trọng. Docker Compose bản mới bỏ qua field `version`, stack vẫn chạy được.

#### Architecture diagram

```text
Client
  |
  v
Nginx :80 / :443
  |
  v
Agent service :8000
  |              |
  v              v
Redis         Qdrant
```

Luồng giao tiếp:

- Client gửi request tới Nginx qua `http://localhost`.
- Nginx reverse proxy request vào service `agent`.
- Agent xử lý request bằng FastAPI.
- Agent có thể giao tiếp với Redis qua `redis://redis:6379/0`.
- Agent có thể giao tiếp với Qdrant qua `http://qdrant:6333`.
- Các service nằm trong Docker network `internal`.

Lệnh chạy stack:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment
docker compose -f 02-docker/production/docker-compose.yml up --build
```

Test qua Nginx:

```powershell
curl.exe http://localhost/health
```

Test agent endpoint qua Nginx trong PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost/ask" -Method Post -ContentType "application/json" -Body '{"question":"Explain microservices"}'
```

Nếu port `80` đang bận, cần dừng service/container đang dùng port đó hoặc đổi port mapping của Nginx.

---

### Debugging commands learned

Một số lệnh debug container hữu ích:

```powershell
docker images my-agent:develop
docker images my-agent:advanced
docker ps
docker ps -a
docker logs <container_name>
docker exec -it <container_name> /bin/sh
docker stop <container_name>
docker compose -f 02-docker/production/docker-compose.yml config
docker compose -f 02-docker/production/docker-compose.yml up --build
docker compose -f 02-docker/production/docker-compose.yml down
```

Trong quá trình làm Part 2, lỗi chính gặp phải là build sai Docker context. Cách debug là đọc lỗi `COPY ... not found`, kiểm tra Dockerfile đang copy path nào, sau đó build lại từ đúng root context.

---

### Checkpoint 2

- [x] Hiểu cấu trúc Dockerfile basic.
- [x] Biết base image, working directory, layer cache và `CMD`.
- [x] Build và run được develop image.
- [x] Test được health endpoint trong container develop.
- [x] Hiểu multi-stage build gồm builder stage và runtime stage.
- [x] Build được production/advanced image.
- [x] So sánh được image size giữa develop và production.
- [x] Hiểu vì sao image nhỏ hơn giúp deploy/startup/scale nhanh hơn và cải thiện UX.
- [x] Hiểu Docker Compose orchestration với agent, Redis, Qdrant và Nginx.
- [x] Biết các lệnh debug container như `docker logs`, `docker ps`, `docker exec`, `docker compose config`.

### Kết luận Part 2

Bản Docker develop giúp đóng gói app vào container và chạy nhất quán, nhưng image còn lớn vì dùng single-stage build với `python:3.11` full. Bản production dùng multi-stage build và `python:3.11-slim`, giúp image giảm từ khoảng `1.66GB` xuống `56.6MB`. Image nhỏ hơn giúp deploy nhanh hơn, startup nhanh hơn, scale tốt hơn, giảm thời gian chờ của user và phù hợp hơn với môi trường cloud production.

---

## Part 3: Cloud Deployment

### Mục tiêu của Part 3

Part 3 giải quyết vấn đề laptop không thể chạy 24/7 và không có public IP ổn định. Khi deploy lên cloud platform, agent có thể chạy liên tục, có public URL để người dùng bên ngoài truy cập, có logs/deployment history và có thể cấu hình bằng environment variables.

Các platform được so sánh trong lab:

| Platform | Độ khó | Free tier | Best for |
|---|---:|---|---|
| Railway | Dễ nhất | $5 credit / trial | Prototype, demo nhanh |
| Render | Trung bình | Có free tier | Side project, demo dài hơn |
| Cloud Run | Khó hơn | Free quota theo request | Production/serverless |

Trong bài này tôi chọn **Railway** để deploy.

---

### Exercise 3.1: Railway deployment

#### Thông tin deployment

- Platform: Railway
- Project: `serene-nurturing`
- Environment: `production`
- Service name: `day12`
- Public URL: `https://day12-production-ac48.up.railway.app`
- Root Directory: `03-cloud-deployment/railway`
- Build method: Nixpacks
- Config file: `railway.toml`
- Health check path: `/health`

File `03-cloud-deployment/railway/railway.toml` cấu hình:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Điểm quan trọng là Railway inject biến môi trường `PORT`, nên app phải chạy với:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

#### Vấn đề gặp phải khi deploy

Ban đầu tôi chọn GitHub repo `batch02-day12_cloud_infras_and_deployment` để deploy. Repo này là dạng monorepo/lab repo, trong đó app Railway nằm sâu ở:

```text
03-cloud-deployment/railway
```

Railway ban đầu build từ root repo nên build fail vì không nhìn đúng `app.py`, `requirements.txt`, `railway.toml`.

Cách fix:

```text
Settings -> Source -> Root Directory
```

Set Root Directory thành:

```text
03-cloud-deployment/railway
```

Sau đó redeploy, service `day12` đã chạy online.

#### Public URL

Railway tạo public domain:

```text
https://day12-production-ac48.up.railway.app
```

Khi mở root URL trên browser:

```text
https://day12-production-ac48.up.railway.app
```

Kết quả:

```json
{"message":"AI Agent running on Railway!","docs":"/docs","health":"/health"}
```

Điều này xác nhận service public đã hoạt động.

#### Health check test

Command:

```powershell
curl.exe https://day12-production-ac48.up.railway.app/health
```

Output:

```json
{"status":"ok","uptime_seconds":559.1,"platform":"Railway","timestamp":"2026-06-12T08:32:12.920556+00:00"}
```

Nhận xét:

- Endpoint `/health` trả `status: ok`.
- Response có `platform: Railway`.
- Service đang chạy trên public URL.
- Health check path phù hợp với `railway.toml`.

#### Agent endpoint test

Command:

```powershell
Invoke-RestMethod -Uri "https://day12-production-ac48.up.railway.app/ask" -Method Post -ContentType "application/json" -Body '{"question":"Hello Railway"}'
```

Output:

```text
question       answer
--------       ------
Hello Railway  Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi...
```

Nhận xét:

- Endpoint `/ask` hoạt động trên public URL.
- App nhận JSON body hợp lệ.
- App trả response từ mock LLM.
- Vì dùng mock LLM nên không cần OpenAI API key thật.

#### Environment variables

Trong bài Railway này:

- `PORT`: Railway tự inject, không cần tự set.
- `ENVIRONMENT`: có thể set là `production` trong Railway Variables.
- `OPENAI_API_KEY`: không bắt buộc vì app dùng mock LLM.
- `AGENT_API_KEY`: chưa bắt buộc trong app Railway hiện tại vì endpoint `/ask` chưa enforce API key.

Tuy nhiên trong production thật, secrets nên được set ở Railway Variables hoặc secret manager, không commit vào source code.

#### Logs và debugging trên Railway

Để xem lỗi build/deploy/runtime:

- Vào service `day12`
- Mở tab `Deployments`
- Chọn deployment mới nhất
- Bấm `View logs`

Trong quá trình làm bài, logs giúp phát hiện deploy fail vì build từ sai root directory.

---

### Exercise 3.2: Compare Render with Railway

Tôi không deploy Render vì đã chọn Railway làm platform chính, nhưng đã đọc `03-cloud-deployment/render/render.yaml` và so sánh với `railway.toml`.

#### Railway config: `railway.toml`

Railway config ngắn gọn hơn:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
restartPolicyType = "ON_FAILURE"
```

Railway tập trung vào service hiện tại: cách build, start command, health check và restart policy.

#### Render config: `render.yaml`

Render config mô tả nhiều infrastructure hơn:

```yaml
services:
  - type: web
    name: ai-agent
    runtime: python
    region: singapore
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: OPENAI_API_KEY
        sync: false
      - key: AGENT_API_KEY
        generateValue: true

  - type: redis
    name: agent-cache
    plan: free
    maxmemoryPolicy: allkeys-lru
```

Render có thể khai báo cả web service, Redis service, region, plan, build command, start command, env vars và auto deploy trong một file.

#### Comparison table

| Tiêu chí | Railway `railway.toml` | Render `render.yaml` |
|---|---|---|
| Độ dài config | Ngắn, đơn giản | Dài hơn, mô tả nhiều infrastructure |
| Build | `builder = "NIXPACKS"` | `buildCommand: pip install -r requirements.txt` |
| Start command | `uvicorn app:app --host 0.0.0.0 --port $PORT` | Tương tự |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Restart policy | Có `restartPolicyType`, `restartPolicyMaxRetries` | Không thấy khai báo restart policy trực tiếp trong file |
| Env vars | Thường set qua Dashboard/CLI | Có thể khai báo env vars trong YAML |
| Secret handling | Set qua Railway Variables | `sync: false` hoặc `generateValue: true` |
| Extra services | File hiện tại chỉ cấu hình app service | Có thể khai báo Redis service cùng Blueprint |
| Phù hợp | Demo/prototype nhanh | Side project có nhiều service hơn |

Kết luận: Railway đơn giản và nhanh hơn cho prototype. Render YAML có tính Infrastructure as Code rõ hơn khi muốn khai báo cả web app và Redis trong cùng một blueprint.

---

### Exercise 3.3: Optional GCP Cloud Run

Tôi không deploy GCP Cloud Run vì bài yêu cầu deploy ít nhất 1 platform và tôi đã deploy thành công Railway. Tuy nhiên tôi đã đọc `cloudbuild.yaml` và `service.yaml` để hiểu CI/CD pipeline.

#### `cloudbuild.yaml`

File này định nghĩa pipeline trên Google Cloud Build:

1. **Run tests**

   Dùng image `python:3.11-slim`, cài requirements và chạy `pytest`.

2. **Build Docker image**

   Dùng `gcr.io/cloud-builders/docker` để build image:

   ```text
   gcr.io/$PROJECT_ID/ai-agent:$COMMIT_SHA
   gcr.io/$PROJECT_ID/ai-agent:latest
   ```

3. **Push image**

   Push image lên Google Container Registry/Artifact Registry.

4. **Deploy to Cloud Run**

   Dùng `gcloud run deploy` để deploy service `ai-agent` với:

   - region `asia-southeast1`
   - public endpoint `--allow-unauthenticated`
   - min instances = 1 để tránh cold start
   - max instances = 10 để giới hạn scale
   - memory 512Mi
   - env vars/secrets từ Secret Manager

#### `service.yaml`

File này là Cloud Run Service Definition theo Knative format. Nó mô tả:

- Service name: `ai-agent`
- Public ingress
- Autoscaling min/max instances
- Container concurrency
- Timeout
- Container image
- CPU/memory request và limit
- Environment variables
- Secrets từ Secret Manager
- Liveness probe `/health`
- Startup probe `/ready`

Kết luận: Cloud Run phức tạp hơn Railway/Render nhưng production-ready hơn vì có CI/CD, autoscaling, resource limits, health probes và secret management rõ ràng.

---

### Checkpoint 3

- [x] Deploy thành công lên ít nhất 1 platform: Railway.
- [x] Có public URL hoạt động: `https://day12-production-ac48.up.railway.app`.
- [x] Test được root endpoint trên browser.
- [x] Test được `/health` bằng curl.
- [x] Test được `/ask` bằng `Invoke-RestMethod`.
- [x] Hiểu cách set Root Directory khi deploy monorepo lên Railway.
- [x] Hiểu cách Railway inject biến môi trường `PORT`.
- [x] Hiểu cách set environment variables trên cloud qua Railway Variables.
- [x] Biết cách xem build/deploy logs trong Railway Deployments.
- [x] Đọc và so sánh được `render.yaml` với `railway.toml`.
- [x] Đọc hiểu cơ bản pipeline Cloud Run qua `cloudbuild.yaml` và `service.yaml`.

### Kết luận Part 3

Tôi đã deploy thành công FastAPI AI Agent lên Railway với public URL `https://day12-production-ac48.up.railway.app`. Ban đầu deployment fail vì Railway build từ root repo thay vì subfolder app, sau đó tôi sửa Root Directory thành `03-cloud-deployment/railway` và redeploy thành công. Public endpoint `/health` trả `status: ok`, endpoint `/ask` nhận câu hỏi và trả mock response. Qua phần này tôi hiểu cách đưa app từ local lên cloud, cách lấy public URL, cách dùng health check, cách xử lý monorepo deployment và cách xem logs/debug trên Railway.

---

## Part 4: API Security

### Mục tiêu của Part 4

Part 4 giải quyết rủi ro khi API agent được public: nếu ai cũng gọi được endpoint, chi phí LLM có thể tăng không kiểm soát. Các lớp bảo vệ chính gồm authentication, rate limiting và cost guard.

Luồng bảo vệ mong muốn:

```text
Request
  -> Auth check
  -> Rate limit check
  -> Input validation
  -> Cost/budget check
  -> Agent response
```

---

### Exercise 4.1: API Key authentication

Folder sử dụng:

```text
04-api-gateway/develop
```

File chính:

```text
04-api-gateway/develop/app.py
```

Trong bản develop, API key được đọc từ environment variable:

```python
API_KEY = os.getenv("AGENT_API_KEY", "demo-key-change-in-production")
```

Header được kiểm tra là:

```text
X-API-Key
```

Logic kiểm tra nằm trong function:

```python
def verify_api_key(api_key: str = Security(api_key_header)) -> str:
```

Endpoint `/ask` yêu cầu dependency này:

```python
_key: str = Depends(verify_api_key)
```

#### Test không có API key

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask?question=Hello" -Method Post
```

Output:

```text
{"detail":"Missing API key. Include header: X-API-Key: "}
INFO: 127.0.0.1 - "POST /ask?question=Hello HTTP/1.1" 401 Unauthorized
```

Nhận xét:

- Request không có `X-API-Key` bị chặn.
- Server trả `401 Unauthorized`.

#### Test có API key đúng

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask?question=Hello" -Method Post -Headers @{"X-API-Key"="secret-key-123"}
```

Output:

```text
question answer
-------- ------
Hello    Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi...
```

Nhận xét:

- Request có key đúng được chấp nhận.
- Endpoint `/ask` trả response thành công.

#### Nếu sai key thì sao?

Nếu header `X-API-Key` khác với `AGENT_API_KEY`, server trả:

```text
403 Invalid API key
```

#### Làm sao rotate key?

Để rotate API key:

1. Tạo key mới.
2. Cập nhật biến môi trường `AGENT_API_KEY`.
3. Restart/redeploy service.
4. Thông báo client dùng key mới.
5. Thu hồi key cũ.

Không nên sửa key trực tiếp trong source code.

---

### Exercise 4.2: JWT authentication

Folder sử dụng:

```text
04-api-gateway/production
```

Các file chính:

```text
auth.py
app.py
```

#### JWT flow

JWT flow trong app:

1. Client gửi username/password tới `POST /auth/token`.
2. Server kiểm tra credential bằng `authenticate_user`.
3. Server tạo JWT bằng `create_token`.
4. JWT chứa `sub`, `role`, `iat`, `exp`.
5. Client gọi endpoint protected với header:

   ```text
   Authorization: Bearer <token>
   ```

6. Server verify token bằng `verify_token`.
7. Nếu token hợp lệ, request tiếp tục đi qua rate limit và cost guard.

Demo users trong `auth.py`:

```text
student / demo123  -> role user
teacher / teach456 -> role admin
```

#### Issue gặp phải và cách fix

Khi chạy bản production, `/health` ban đầu trả `Internal Server Error`. Nguyên nhân nằm trong middleware security headers:

```python
response.headers.pop("server", None)
```

`response.headers` không hoạt động như dict thường với `.pop()`. Tôi đã sửa thành:

```python
if "server" in response.headers:
    del response.headers["server"]
```

Sau khi restart app, các endpoint production hoạt động bình thường.

#### Test lấy token

Command:

```powershell
$tokenResponse = Invoke-RestMethod -Uri "http://localhost:8000/auth/token" -Method Post -ContentType "application/json" -Body '{"username":"student","password":"demo123"}'
$TOKEN = $tokenResponse.access_token
```

Kết quả: lấy token thành công.

#### Test gọi `/ask` bằng JWT

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method Post -ContentType "application/json" -Headers @{"Authorization"="Bearer $TOKEN"} -Body '{"question":"Explain JWT"}'
```

Output:

```text
question    answer
--------    ------
Explain JWT Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi...
```

Nhận xét:

- `/ask` không dùng API key ở bản production.
- `/ask` yêu cầu JWT Bearer token.
- Token hợp lệ giúp request được xử lý thành công.

---

### Exercise 4.3: Rate limiting

File cần đọc:

```text
04-api-gateway/production/rate_limiter.py
```

Algorithm được dùng là:

```text
Sliding Window Counter
```

Cách hoạt động:

- Mỗi user có một deque lưu timestamps của các request.
- Trước mỗi request, app loại bỏ timestamp cũ ngoài window 60 giây.
- Nếu số request trong window đã đạt limit, server trả `429 Too Many Requests`.
- Nếu chưa vượt limit, timestamp hiện tại được thêm vào window.

Limits:

```text
User: 10 requests / 60 seconds
Admin: 100 requests / 60 seconds
```

Admin không bypass hoàn toàn rate limit, nhưng được dùng limiter riêng với limit cao hơn.

Trong `app.py`:

```python
limiter = rate_limiter_admin if role == "admin" else rate_limiter_user
rate_info = limiter.check(username)
```

#### Test rate limit với student

Command:

```powershell
for ($i = 1; $i -le 20; $i++) {
  try {
    Invoke-RestMethod -Uri "http://localhost:8000/ask" `
      -Method Post `
      -ContentType "application/json" `
      -Headers @{"Authorization"="Bearer $TOKEN"} `
      -Body "{`"question`":`"Test $i`"}" | Out-Null

    "Request $i OK"
  } catch {
    $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "NO_RESPONSE" }
    $body = $_.ErrorDetails.Message
    "Request $i FAILED: $status $body"
  }
}
```

Output:

```text
Request 1 OK
Request 2 OK
Request 3 OK
Request 4 OK
Request 5 OK
Request 6 OK
Request 7 OK
Request 8 OK
Request 9 OK
Request 10 OK
Request 11 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 12 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 13 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 14 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 15 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 16 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 17 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 18 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 19 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Request 20 FAILED: 429 {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Nhận xét:

- 10 request đầu thành công.
- Request 11 trở đi bị chặn với status `429`.
- Response trả thông tin limit, window và retry-after.
- Rate limiter hoạt động đúng như thiết kế `10 req/min`.

#### Test admin stats

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/admin/stats" `
  -Method Get `
  -Headers @{"Authorization"="Bearer $ADMIN_TOKEN"}
```

Output:

```text
total_users           global_cost_usd       global_budget_usd
-----------           ---------------       -----------------
N/A (in-memory demo)  0.00017639999999999995 10.0
```

Nhận xét:

- Admin token truy cập được endpoint `/admin/stats`.
- Endpoint trả global cost hiện tại và global budget.

---

### Exercise 4.4: Cost guard

File cần đọc:

```text
04-api-gateway/production/cost_guard.py
```

Trong lab text, cost guard concept yêu cầu:

- Mỗi user có budget `$10/tháng`.
- Track spending trong Redis.
- Reset đầu tháng.

Trong code hiện tại, implementation là bản demo in-memory:

- Per-user daily budget: `$1/day`.
- Global daily budget: `$10/day`.
- Track usage trong dict `_records`.
- Reset theo ngày bằng `YYYY-MM-DD`.
- Nếu user vượt budget, trả `402 Payment Required`.
- Nếu global budget vượt limit, trả `503 Service temporarily unavailable`.

Trong endpoint `/ask`, flow cost guard là:

```python
cost_guard.check_budget(username)
response_text = ask(body.question)
usage = cost_guard.record_usage(username, input_tokens, output_tokens)
```

#### Test usage endpoint

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/me/usage" `
  -Method Get `
  -Headers @{"Authorization"="Bearer $TOKEN"}
```

Output:

```text
user_id              : student
date                 : 2026-06-12
requests             : 1
input_tokens         : 4
output_tokens        : 26
cost_usd             : 1.6E-05
budget_usd           : 1.0
budget_remaining_usd : 0.999984
budget_used_pct      : 0.0
```

Nhận xét:

- App ghi nhận số request.
- App ước tính input/output tokens.
- App tính cost USD.
- App trả budget còn lại.

#### Test không có token

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/me/usage" -Method Get
```

Output:

```text
{"detail":"Authentication required. Include: Authorization: Bearer "}
```

Nhận xét:

- Usage endpoint được bảo vệ bằng JWT.
- Thiếu token sẽ bị chặn.

#### Ghi chú production

Implementation hiện tại dùng in-memory store nên phù hợp demo nhưng chưa phù hợp khi scale nhiều instances. Trong production thật, cost guard nên lưu usage trong Redis hoặc database để mọi instance cùng nhìn thấy cùng một trạng thái budget.

---

### Discussion questions

#### 1. Khi nào nên dùng API Key vs JWT vs OAuth2?

- API Key phù hợp cho internal API, B2B integration, service-to-service hoặc MVP đơn giản.
- JWT phù hợp khi có user login, role, token expiry và stateless authentication.
- OAuth2 phù hợp khi cần login qua bên thứ ba, delegated access hoặc hệ thống nhiều client/app.

#### 2. Rate limit nên đặt bao nhiêu request/phút cho AI agent?

Tùy use case và chi phí model. Với demo/lab, `10 req/min` cho user thường là hợp lý để tránh spam. Với admin hoặc internal testing có thể cao hơn, ví dụ `100 req/min`. Trong production nên dựa trên chi phí LLM, latency, quota và hành vi người dùng thật.

#### 3. Nếu API key bị lộ, phát hiện và xử lý thế nào?

Cần kiểm tra logs/usage bất thường, revoke key cũ, tạo key mới, cập nhật client, audit commit history và secret scanning. Nếu key từng nằm trong Git history, cần rotate key ngay vì xóa file hiện tại chưa đủ.

---

### Checkpoint 4

- [x] Implement/test API key authentication.
- [x] Hiểu JWT flow và test được `/auth/token`.
- [x] Gọi được protected endpoint `/ask` bằng Bearer token.
- [x] Hiểu role user/admin.
- [x] Implement/test rate limiting với Sliding Window Counter.
- [x] Quan sát được `429 Rate limit exceeded` sau 10 requests/minute.
- [x] Test được admin stats bằng admin token.
- [x] Hiểu cost guard và xem được usage qua `/me/usage`.
- [x] Biết hạn chế của in-memory cost guard và lý do nên dùng Redis/database trong production.

### Kết luận Part 4

Part 4 đã bổ sung các lớp bảo vệ quan trọng cho public AI Agent. Bản develop dùng API Key đơn giản để chặn request không hợp lệ. Bản production dùng JWT authentication, role-based rate limiting và cost guard. Test thực tế cho thấy request thiếu API key bị `401`, request có API key đúng thành công, JWT token gọi được `/ask`, rate limit chặn request thứ 11 với `429`, và cost guard ghi nhận usage/cost theo user. Đây là nền tảng cần thiết để tránh việc public URL bị lạm dụng và gây phát sinh chi phí LLM ngoài kiểm soát.

---

## Part 5: Scaling & Reliability

### Mục tiêu của Part 5

Part 5 tập trung vào việc làm cho agent có thể chạy ổn định khi có nhiều người dùng. Một instance đơn lẻ có thể không đủ khi traffic tăng, vì vậy app cần có health checks, readiness checks, graceful shutdown, stateless design, Redis để lưu state ngoài process và Nginx để load balance nhiều agent instances.

Các concept chính:

- **Health checks:** platform biết process còn sống hay cần restart.
- **Readiness checks:** load balancer biết instance đã sẵn sàng nhận traffic chưa.
- **Graceful shutdown:** hoàn thành request đang xử lý trước khi tắt.
- **Stateless design:** không lưu state quan trọng trong memory của một instance.
- **Load balancing:** phân tán request qua nhiều instances.
- **Redis-backed session:** mọi instance cùng đọc/ghi conversation history từ Redis.

---

### Exercise 5.1: Health checks

Folder sử dụng:

```text
05-scaling-reliability/develop
```

File chính:

```text
05-scaling-reliability/develop/app.py
```

Trong bản develop, app đã implement:

- `GET /health`: liveness probe.
- `GET /ready`: readiness probe.
- Middleware đếm số request đang xử lý bằng `_in_flight_requests`.

#### Test `/health`

Command:

```powershell
curl.exe http://localhost:8000/health
```

Output:

```json
{"status":"degraded","uptime_seconds":10.8,"version":"1.0.0","environment":"development","timestamp":"2026-06-12T09:08:58.242595+00:00","checks":{"memory":{"status":"degraded","used_percent":90.3}}}
```

Nhận xét:

- Endpoint `/health` hoạt động.
- App trả thông tin uptime, version, environment và timestamp.
- Status là `degraded` vì memory trên máy đang dùng khoảng `90.3%`.
- Đây không có nghĩa app chết; health check đang phản ánh resource pressure của môi trường chạy.

#### Test `/ready`

Command:

```powershell
curl.exe http://localhost:8000/ready
```

Output:

```json
{"ready":true,"in_flight_requests":1}
```

Nhận xét:

- Endpoint `/ready` hoạt động.
- `ready: true` nghĩa là instance đã sẵn sàng nhận traffic.
- `in_flight_requests` cho biết số request đang xử lý tại thời điểm gọi.

#### Test `/ask`

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask?question=Hello" -Method Post
```

Output:

```text
answer
------
Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response...
```

Nhận xét:

- App vẫn xử lý request bình thường khi readiness là `true`.

---

### Exercise 5.2: Graceful shutdown

Trong `develop/app.py`, graceful shutdown được xử lý qua FastAPI lifespan và signal handlers:

- Startup: app load model/dependencies, sau đó set `_is_ready = True`.
- Shutdown: app set `_is_ready = False`, chờ in-flight requests hoàn thành, sau đó shutdown.
- Signal handler log khi nhận `SIGTERM` hoặc `SIGINT`.

Output khi shutdown:

```text
2026-06-12 16:09:35,807 INFO 🔄 Graceful shutdown initiated...
2026-06-12 16:09:35,808 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [22084]
2026-06-12 16:09:35,809 INFO Received signal 2 — uvicorn will handle graceful shutdown
```

Nhận xét:

- App nhận shutdown signal.
- Lifespan shutdown chạy.
- App log quá trình graceful shutdown.
- Uvicorn hoàn tất application shutdown thay vì tắt đột ngột.

Điều này quan trọng trong production vì khi deploy/restart/scale down container, request đang xử lý có cơ hội hoàn thành trước khi process dừng.

---

### Exercise 5.3: Stateless design

Folder sử dụng:

```text
05-scaling-reliability/production
```

File chính:

```text
05-scaling-reliability/production/app.py
```

Bản production implement stateless session bằng Redis:

- App không lưu conversation history trong memory của riêng một instance.
- Session được lưu bằng key dạng:

  ```text
  session:<session_id>
  ```

- Function `save_session` ghi session vào Redis.
- Function `load_session` đọc session từ Redis.
- Function `append_to_history` thêm message vào conversation history.

Nếu Redis available:

```text
storage = redis
```

Nếu Redis không available, app fallback sang in-memory store, nhưng mode này không phù hợp để scale nhiều instances.

Tại sao stateless quan trọng:

- Khi có nhiều agent instances, request 1 có thể vào `instance A`, request 2 có thể vào `instance B`.
- Nếu state nằm trong memory, `instance B` sẽ không có conversation history từ `instance A`.
- Khi state nằm trong Redis, mọi instance đều đọc/ghi chung một session store.

---

### Exercise 5.4: Load balancing

Production stack dùng:

```text
05-scaling-reliability/production/docker-compose.yml
```

Các service chính:

1. **agent**

   FastAPI stateless agent. Có thể scale thành nhiều replicas.

2. **redis**

   Shared session store cho conversation history.

3. **nginx**

   Reverse proxy/load balancer, expose ra host qua port `8080`.

Tôi đã chuẩn hóa cấu hình để stack chạy được:

- Thêm `05-scaling-reliability/production/Dockerfile`.
- Thêm `05-scaling-reliability/production/requirements.txt`.
- Sửa `docker-compose.yml` để build đúng:

  ```yaml
  build:
    context: ../..
    dockerfile: 05-scaling-reliability/production/Dockerfile
  ```

Lệnh chạy stack:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment
docker compose -f 05-scaling-reliability/production/docker-compose.yml up --build --scale agent=3
```

Architecture:

```text
Client
  |
  v
Nginx localhost:8080
  |
  v
agent service replicas
  |       |       |
  v       v       v
Redis shared session store
```

Nginx config dùng upstream:

```nginx
upstream agent_cluster {
    server agent:8000;
    keepalive 16;
}
```

Docker Compose DNS sẽ resolve service name `agent` tới các agent containers, giúp Nginx phân phối request.

#### Test health qua Nginx

Command:

```powershell
curl.exe http://localhost:8080/health
```

Output:

```json
{"status":"ok","instance_id":"instance-9b8043","uptime_seconds":13.1,"storage":"redis","redis_connected":true}
```

Nhận xét:

- Nginx route request tới một agent instance.
- Agent dùng Redis làm storage.
- Redis connected là `true`.
- `instance_id` cho biết instance cụ thể xử lý request.

#### Test readiness qua Nginx

Command:

```powershell
curl.exe http://localhost:8080/ready
```

Output:

```json
{"ready":true,"instance":"instance-fd1e44"}
```

Nhận xét:

- Readiness check qua load balancer hoạt động.
- Request `/ready` được xử lý bởi instance khác với `/health`, chứng minh load balancing đang phân phối request.

#### Test chat qua Nginx

Command:

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/chat" -Method Post -ContentType "application/json" -Body '{"question":"What is Docker?"}'
```

Output:

```text
session_id : e395fb38-81b5-48c1-9ba5-7be53c4bdbf7
question   : What is Docker?
answer     : Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!
turn       : 2
served_by  : instance-eff183
storage    : redis
```

Nhận xét:

- Endpoint `/chat` hoạt động qua Nginx.
- Response có `session_id`.
- Response có `served_by`, cho biết instance xử lý request.
- Response có `storage: redis`, xác nhận session state được lưu ngoài app instance.

---

### Exercise 5.5: Test stateless

Script sử dụng:

```text
05-scaling-reliability/production/test_stateless.py
```

Command:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment\05-scaling-reliability\production
python test_stateless.py
```

Output:

```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 4e18927e-00e0-4ef3-b24a-dbc570e4af3d

Request 1: [instance-9b8043]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-fd1e44]
  Q: Why do we need containers?
  A: Đây là câu trả lời từ AI agent (mock)...

Request 3: [instance-eff183]
  Q: What is Kubernetes?
  A: Tôi là AI agent được deploy lên cloud...

Request 4: [instance-9b8043]
  Q: How does load balancing work?
  A: Agent đang hoạt động tốt! (mock response)...

Request 5: [instance-fd1e44]
  Q: What is Redis used for?
  A: Đây là câu trả lời từ AI agent (mock)...

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-eff183', 'instance-fd1e44', 'instance-9b8043'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Đây là câu trả lời từ AI agent (mock)...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud...
  [user]: How does load balancing work?...
  [assistant]: Agent đang hoạt động tốt! (mock response)...
  [user]: What is Redis used for?...
  [assistant]: Đây là câu trả lời từ AI agent (mock)...

✅ Session history preserved across all instances via Redis!
```

Nhận xét:

- 5 requests được xử lý bởi 3 instances khác nhau:

  ```text
  instance-9b8043
  instance-fd1e44
  instance-eff183
  ```

- Dù request đi qua nhiều instances, session history vẫn đầy đủ.
- Conversation history có 10 messages, gồm 5 user messages và 5 assistant messages.
- Điều này chứng minh state không phụ thuộc vào memory của từng instance mà được lưu trong Redis.

---

### Debugging note

Khi chạy:

```powershell
docker compose -f 05-scaling-reliability/production/docker-compose.yml logs agent
```

từ folder:

```text
05-scaling-reliability/production
```

Docker báo lỗi vì path bị lặp:

```text
...\production\05-scaling-reliability\production\docker-compose.yml
```

Cách chạy đúng nếu đang ở root repo:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment
docker compose -f 05-scaling-reliability/production/docker-compose.yml logs agent
```

Cách chạy đúng nếu đang ở folder production:

```powershell
cd D:\Vin\batch02-day12_cloud_infras_and_deployment\05-scaling-reliability\production
docker compose -f docker-compose.yml logs agent
```

---

### Checkpoint 5

- [x] Implement/test health check endpoint `/health`.
- [x] Implement/test readiness endpoint `/ready`.
- [x] Quan sát được health status `degraded` khi memory usage cao.
- [x] Test được graceful shutdown qua log shutdown.
- [x] Hiểu vì sao stateless design quan trọng khi scale nhiều instances.
- [x] Chạy được production stack với Nginx, Redis và nhiều agent instances.
- [x] Test được `/health`, `/ready`, `/chat` qua Nginx ở port `8080`.
- [x] Quan sát request được xử lý bởi nhiều `instance_id` khác nhau.
- [x] Xác nhận `storage: redis` và `redis_connected: true`.
- [x] Chạy `test_stateless.py` thành công.
- [x] Xác nhận conversation history được giữ nguyên dù request đi qua nhiều instances.

### Kết luận Part 5

Part 5 chứng minh agent đã có các khả năng quan trọng để scale và chạy ổn định hơn trong production. Bản develop có health check, readiness check và graceful shutdown. Bản production dùng Redis để lưu session/history, giúp app stateless và có thể scale nhiều replicas. Khi chạy stack với Nginx load balancer và 3 agent instances, request được phân phối qua nhiều instances khác nhau nhưng conversation history vẫn được giữ nguyên trong Redis. Điều này giải quyết vấn đề một instance không đủ khi có nhiều users và tránh lỗi mất state khi load balancing.
