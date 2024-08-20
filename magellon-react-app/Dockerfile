# Stage 1: Build the application
FROM node:20-alpine as build

# Set working directory
WORKDIR /app
ARG API_URL
# Copy package.json and package-lock.json (if available)
COPY package*.json ./

# Copy the rest of the application
COPY ./ /app/
COPY ./nginx.conf /app/nginx/

# If API_URL is provided, perform the replacement
#RUN if [ -n "${API_URL}" ]; then \
#      sed -i "s|http://backend:8000/web/|${API_URL}|g" /app/src/environments/environment.prod.ts; \
#    fi

# Install dependencies
RUN npm install

# Build the application
RUN npm run build

# Stage 2: Serve the application
FROM nginx:alpine

# Copy built files from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config (optional)
COPY nginx.conf /etc/nginx/conf.d/default.conf

#COPY --from=build /app/dist/magellon-app /usr/share/nginx/html
#COPY --from=build /app/nginx/nginx.conf /etc/nginx/conf.d/default.conf

ENV API_URL="${API_URL}"
# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
