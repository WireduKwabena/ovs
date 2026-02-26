FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=/api
ARG VITE_INTERVIEW_WS_URL=
ARG VITE_FASTAPI_WS=
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_INTERVIEW_WS_URL=${VITE_INTERVIEW_WS_URL}
ENV VITE_FASTAPI_WS=${VITE_FASTAPI_WS}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -q --spider http://127.0.0.1 || exit 1
