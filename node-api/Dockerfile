FROM node:22-slim

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev --no-fund --no-audit

COPY . .

EXPOSE 4000

CMD ["node", "server.js"]
