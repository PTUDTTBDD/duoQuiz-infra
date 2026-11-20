# duoQuiz-infra

Hạ tầng Docker, Docling PDF sidecar và Shared OpenAPI Contract cho hệ thống **DuoQuiz** (tổ chức `PTUDTTBDD`).

## Quy ước Port PostgreSQL

- **Bên trong Docker network (`duoquiz-net`):** `postgres:5432`
- **Từ máy local (host Windows/macOS/Linux):** `localhost:5434` (`ports: 5434:5432`)

## Khởi chạy môi trường phát triển

```bash
cp .env.example .env
docker compose up -d postgres redis minio minio-init
```

Để chạy toàn bộ hệ thống (gồm `docling-service`, `backend-api`, `backend-worker`):

```bash
docker compose up -d --build
```

Kiểm tra nhanh health endpoint:

```bash
curl http://localhost:4000/api/v1/health
```
