FROM node:21-alpine AS builder
WORKDIR /app
COPY package.json yarn.lock package-lock.json svelte.config.js ./
RUN mkdir static
RUN yarn install 
# --immutable --immutable-cache --check-cache
#RUN npm ci --only=production
COPY . .
RUN npm run smui-theme
RUN npm run build

FROM node:21-alpine AS runtime
ENV NODE_ENV production
USER node
WORKDIR /app
COPY --from=builder --chown=node:node /app/build ./build
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node package.json .
ENV PORT 3000
EXPOSE ${PORT}


CMD ["node", "build"]