# Stage 1: Build the application
FROM node:20.16.0 as build
# Install pnpm with corepack
RUN corepack enable && corepack prepare pnpm@latest --activate

# Enable `pnpm add --global` on Alpine Linux by setting
# home location environment variable to a location already in $PATH
# https://github.com/pnpm/pnpm/issues/784#issuecomment-1518582235
ENV PNPM_HOME=/usr/local/bin

# Add a global package
RUN pnpm add --global @upleveled/preflight@latest

#SHELL ["zsh", "-c"]
#SHELL ["/bin/bash", "-c"]
# Set working directory
WORKDIR /app
ARG API_URL
# Copy package.json and pnpm-lock.yaml (if available)
COPY package.json pnpm-lock.yaml ./

# Copy the rest of the application
COPY ./ /app/
COPY ./nginx.conf /app/nginx/

# If API_URL is provided, perform the replacement
#RUN if [ -n "${API_URL}" ]; then \
#      sed -i "s|http://backend:8000/web/|${API_URL}|g" /app/src/environments/environment.prod.ts; \
#    fi
RUN pnpm install -g typescript
# Install dependencies
RUN pnpm install

# Build the application
RUN pnpm run build

# Stage 2: Serve the application
FROM nginx:alpine
# Copy custom nginx config (optional)
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy built files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

#COPY --from=build /app/dist/magellon-app /usr/share/nginx/html
#COPY --from=build /app/nginx/nginx.conf /etc/nginx/conf.d/default.conf

ENV API_URL="${API_URL}"
# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
