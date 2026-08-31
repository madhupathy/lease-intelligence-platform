FROM node:20-alpine AS web-build

WORKDIR /app

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM nginx:alpine

RUN apk add --no-cache gettext

COPY gateway/nginx.conf.template /etc/nginx/nginx.conf.template
COPY gateway/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --from=web-build /app/dist /usr/share/nginx/html

# Default listen port; Railway overrides via $PORT.
ENV PORT=8080
ENV EXTRACTION_UPSTREAM=extraction:8000
ENV RISK_ENGINE_UPSTREAM=risk-engine:8081

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
