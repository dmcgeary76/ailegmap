# Static build of the map, served by nginx. Needs docs/data.json from the repo
# root, so build from the repository root:  docker build -f frontend/Dockerfile .
FROM node:20-alpine AS build
WORKDIR /src
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY docs/data.json /docs/data.json
RUN VITE_DATA_URL=./data.json npm run build && cp /docs/data.json dist/data.json

FROM nginx:alpine
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
