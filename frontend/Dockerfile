# ---- Build stage ----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# ---- Runtime stage ---------------------------------------------------------
FROM nginx:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html

# The nginx image entrypoint renders /etc/nginx/templates/*.template through
# envsubst into /etc/nginx/conf.d/ before starting. The FILTER restricts
# substitution to APP_API_TOKEN so nginx's own $host/$remote_addr/etc. are left
# alone. Unset APP_API_TOKEN renders an empty bearer, which the backend ignores
# when it has no token configured (local dev / CI).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER=APP_API_TOKEN
ENV APP_API_TOKEN=""

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
