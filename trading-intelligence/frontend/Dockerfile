FROM node:24-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
CMD ["node", "node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0"]
