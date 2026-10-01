FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

EXPOSE 3000

# Run dev server in container (proxied to backend)
CMD ["npm", "run", "dev"]
