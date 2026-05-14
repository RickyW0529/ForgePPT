# 04 - Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

---

- [ ] **Step 1: Write Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 2: Test build**

Run: `docker compose build frontend`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat: add frontend Dockerfile"
```
