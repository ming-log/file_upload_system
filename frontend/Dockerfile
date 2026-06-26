FROM node:20-alpine AS build

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" NO_PROXY="$NO_PROXY" \
    http_proxy="$http_proxy" https_proxy="$https_proxy" no_proxy="$no_proxy" \
    corepack enable \
    && HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" NO_PROXY="$NO_PROXY" \
    http_proxy="$http_proxy" https_proxy="$https_proxy" no_proxy="$no_proxy" \
    corepack prepare pnpm@10.33.0 --activate \
    && pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
