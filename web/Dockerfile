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
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Included by BOTH server blocks, and by the locations that set an
# add_header of their own -- nginx drops inherited headers there.
COPY security-headers.conf /etc/nginx/security-headers.conf

# The TLS server ships as a TEMPLATE outside conf.d. 40-enable-ssl.sh installs
# it only once a certificate exists -- see that script for why it is a watcher
# and not a startup check. nginx's own entrypoint runs everything in
# /docker-entrypoint.d in order before starting the master process.
COPY ssl.conf.template /etc/nginx/ssl.conf.template
COPY 40-enable-ssl.sh /docker-entrypoint.d/40-enable-ssl.sh

# redirect.d must EXIST even while it is empty. `include` with a wildcard is
# happy to match nothing, but nginx fails to start if the directory itself is
# missing -- so a box that has never had a certificate would not boot at all.
RUN chmod +x /docker-entrypoint.d/40-enable-ssl.sh \
    && mkdir -p /etc/nginx/redirect.d

EXPOSE 80 443
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O- http://localhost:80/ >/dev/null || exit 1
