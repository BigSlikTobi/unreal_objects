FROM node:20-alpine AS build

WORKDIR /app/ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui /app/ui
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/ui-nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/ui/dist /usr/share/nginx/html

CMD ["sh", "-c", "test -n \"$RULE_ENGINE_UPSTREAM\" && test -n \"$DECISION_CENTER_UPSTREAM\" && test -n \"$INTERNAL_API_KEY\" && DNS_RESOLVER=$(awk '/^nameserver/{found=1; addr=$2; if(addr ~ /:/){addr=\"[\"addr\"]\"}; print addr; exit} END{if(!found) exit 1}' /etc/resolv.conf || echo '8.8.8.8') && sed -e \"s|__PORT__|${PORT:-8080}|g\" -e \"s|__RULE_ENGINE_UPSTREAM__|${RULE_ENGINE_UPSTREAM}|g\" -e \"s|__DECISION_CENTER_UPSTREAM__|${DECISION_CENTER_UPSTREAM}|g\" -e \"s|__INTERNAL_API_KEY__|${INTERNAL_API_KEY}|g\" -e \"s|__DNS_RESOLVER__|${DNS_RESOLVER}|g\" /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
