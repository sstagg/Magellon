# Stage 1: Build the application
FROM node:20.9.0-alpine as build
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
RUN corepack prepare pnpm@latest --activate

RUN apk add --no-cache git
#RUN npm install --global yarn

WORKDIR /app
ARG API_URL
# Copy package.json and pnpm-lock.yaml (if available)
COPY package.json pnpm-lock.yaml ./

# Copy the rest of the application
COPY ./ /app/
COPY ./nginx.conf /app/nginx/

# If API_URL is provided, perform the replacement
RUN if [ -n "${API_URL}" ]; then \
      sed -i "s|http://127.0.0.1:8000|${API_URL}|g" /app/src/config/configs.json; \
    fi

#RUN cp /app/src/config/configs.json /app/configs.json
# Install dependencies
#RUN pnpm install
RUN pnpm install --force
#RUN yarn install

# Build the application
RUN npm run build
#RUN vite build



# Stage 2: Serve the application
FROM nginx:alpine
# Copy custom nginx config (optional)
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy built files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html
#COPY --from=build /app/configs.json /usr/share/nginx/html/configs.json

#COPY --from=build /app/nginx/nginx.conf /etc/nginx/conf.d/default.conf

ENV API_URL="${API_URL}"
# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
