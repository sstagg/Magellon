# Stage 1: Build the application
FROM node:22-alpine as build
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
RUN corepack prepare pnpm@latest --activate

RUN apk add --no-cache git
#RUN npm install --global yarn

WORKDIR /app
# Copy package.json and pnpm-lock.yaml (if available)
COPY package.json pnpm-lock.yaml ./

# Copy the rest of the application
COPY src ./src
COPY public ./public
COPY index.html ./
COPY vite.config.ts ./
COPY tsconfig.json ./
COPY tsconfig.node.json ./
# COPY postcss.config.js ./
# COPY tailwind.config.js ./
COPY playwright.config.ts ./

COPY nginx.conf ./nginx.conf

# API host is injected at CONTAINER START via docker-entrypoint.sh
# (config.js from env vars) — no build-time source patching, one image
# runs against any backend.

RUN pnpm install --force --config.dangerouslyAllowAllBuilds=true

# Build the application
RUN npm run build
#RUN vite build



# Stage 2: Serve the application
FROM nginx:alpine
# Copy custom nginx config (optional)
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy built files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint-magellon.sh
RUN sed -i 's/\r$//' /docker-entrypoint-magellon.sh && chmod +x /docker-entrypoint-magellon.sh

# Expose port 80
EXPOSE 80

# Generate /config.js from env, then start nginx.
CMD ["/docker-entrypoint-magellon.sh"]
