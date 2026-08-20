#!/bin/sh
# Turn on the TLS server, but only once a real certificate exists.
#
# WHY A WATCHER RATHER THAN A STARTUP CHECK
# -----------------------------------------
# There is a chicken and egg here. certbot proves control of the hostname over
# HTTP, so nginx has to be serving port 80 BEFORE the certificate can be
# issued -- which means on a first deploy nginx necessarily starts with no
# certificate to load. A one-shot check at startup would therefore never enable
# TLS until somebody restarted the container by hand.
#
# So this backgrounds a loop. nginx comes up on port 80 exactly as it does
# today, certbot gets the certificate a few seconds later, and the loop notices
# and reloads. Renewals are picked up the same way, without a restart.
#
# WHY THIS CANNOT TAKE THE SITE DOWN
# ----------------------------------
# * conf.d/ssl.conf is written only when both certificate files are present, so
#   nginx is never asked to load a path that does not exist.
# * The config is tested with `nginx -t` before the reload. A bad template
#   leaves the running configuration untouched.
# * `nginx -s reload` re-execs workers; if it fails the master keeps serving the
#   old configuration. Port 80 does not blink either way.
set -eu

DOMAIN="${TLS_DOMAIN:-}"
LIVE="/etc/letsencrypt/live/${DOMAIN}"
TEMPLATE="/etc/nginx/ssl.conf.template"
TARGET="/etc/nginx/conf.d/ssl.conf"

if [ -z "$DOMAIN" ]; then
    echo "40-enable-ssl: TLS_DOMAIN unset, serving HTTP only"
    exit 0
fi

watch_for_cert() {
    # First minute: check often, so a first deploy gets TLS quickly.
    # After that: every ten minutes, which is ample for a 90-day renewal.
    i=0
    while :; do
        if [ -f "$LIVE/fullchain.pem" ] && [ -f "$LIVE/privkey.pem" ]; then
            if [ ! -f "$TARGET" ]; then
                sed "s|\${DOMAIN}|${DOMAIN}|g" "$TEMPLATE" > "$TARGET"
                if nginx -t 2>/dev/null; then
                    # `|| true` matters: this loop runs under `set -e`, and a
                    # reload can fail simply because nginx has not finished
                    # starting yet. Without it the watcher would exit on the
                    # first attempt and TLS would never come up.
                    nginx -s reload || true
                    echo "40-enable-ssl: certificate found, TLS enabled for ${DOMAIN}"
                else
                    # Do not leave a broken file where the next reload would
                    # pick it up.
                    rm -f "$TARGET"
                    echo "40-enable-ssl: generated config failed nginx -t, staying on HTTP"
                fi
            else
                # Already enabled. Reload anyway on the slow cadence so a
                # renewed certificate is picked up without a restart.
                nginx -t 2>/dev/null && nginx -s reload || true
            fi
        fi
        i=$((i + 1))
        if [ "$i" -lt 12 ]; then sleep 5; else sleep 600; fi
    done
}

watch_for_cert &
echo "40-enable-ssl: watching for a certificate for ${DOMAIN}"
