FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production 2>/dev/null || npm install

COPY . .

RUN npm run build 2>/dev/null || echo "Build skipped in dev mode"

EXPOSE 3000

HEALTHCHECK --interval=20s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:3000 || exit 1

CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
