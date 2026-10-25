FROM node:24-trixie-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

FROM ghcr.io/chamvi/node:24
COPY --from=deps /app/node_modules /app/node_modules
COPY package.json /app/package.json
COPY dist /app/dist
CMD ["node", "node_modules/@chamvi/cli/dist/cli.mjs", "start"]
