# ClauseGuard frontend.
#
#   docker build -t clauseguard-web --build-arg BACKEND_URL=http://api:8000 ./frontend
#
# BACKEND_URL is baked at build time: Next.js rewrites are serialized into
# the standalone build, so the API origin must be known when the image is
# built (docker-compose.full.yml passes the service name).

FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG BACKEND_URL=http://api:8000
ENV BACKEND_URL=$BACKEND_URL
RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app
# Next's standalone server binds to $HOSTNAME, which Docker sets to the
# container id unless overridden; listen on all interfaces. $PORT is
# honoured too, so platforms that inject it (Railway) need no CMD change.
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Next standalone output: server.js + the minimal node_modules subset.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
