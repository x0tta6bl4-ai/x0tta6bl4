# Multi-stage Dockerfile for x0tta6bl4-app (Frontend + API Bridge)

# Stage 1: Build Frontend
FROM node:22-alpine as frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm install --silent
COPY . ./
RUN npm run build

# Stage 2: Production Image
FROM node:22-alpine
LABEL maintainer="x0tta6bl4 Team <contact@x0tta6bl4.net>"
LABEL version="1.0.0"
LABEL description="Cyber-Grid UI and API Bridge for x0tta6bl4 Mesh"

# Install python3 and dependencies for VPN scripts
RUN apk add --no-cache python3 py3-pip curl iptables iproute2 iputils

# Use existing node user
RUN mkdir -p /app /app/dist && chown -R node:node /app

WORKDIR /app

# Copy production node dependencies
COPY package*.json ./
RUN npm install --production --silent

# Copy build files from Stage 1
COPY --from=frontend-builder /app/dist ./dist

# Copy server logic
COPY server.cjs ./

# Switch to non-root user
USER node

# Expose API/Web port (internally 3000)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 CMD curl -f http://localhost:8080/api/status || exit 1

CMD ["node", "server.cjs"]
