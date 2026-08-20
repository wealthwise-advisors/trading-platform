# AutoTrader React frontend -- production static build served by nginx.
# Builds with the same `npm run build` used in local dev (Vite + tsc), then
# ships only the static output -- no Node runtime in the final image.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# A TEMPLATE, not a finished config. The nginx image runs envsubst over
# everything in /etc/nginx/templates at startup and writes the result into
# conf.d, which is how ${TLS_DOMAIN} reaches the config -- nginx cannot read
# environment variables by itself.
#
# NGINX_ENVSUBST_FILTER (set in docker-compose.yml) restricts substitution to
# that ONE variable. Without it envsubst would also eat $uri, $host and
# $request_uri, and the config would be silently rewritten into nonsense.
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template

# The TLS server ships as a TEMPLATE outside conf.d. 40-enable-ssl.sh installs
# it only once a certificate exists -- see that script for why it is a watcher
# and not a startup check. nginx's own entrypoint runs everything in
# /docker-entrypoint.d in order before starting the master process.
COPY ssl.conf.template /etc/nginx/ssl.conf.template
COPY 40-enable-ssl.sh /docker-entrypoint.d/40-enable-ssl.sh
RUN chmod +x /docker-entrypoint.d/40-enable-ssl.sh

EXPOSE 80 443
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O- http://localhost:80/ >/dev/null || exit 1
