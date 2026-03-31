FROM node:20-alpine AS build

WORKDIR /app/ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui /app/ui
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/ui-nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/ui/dist /usr/share/nginx/html

CMD ["sh", "-c", "sed \"s/__PORT__/${PORT:-8080}/g\" /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
