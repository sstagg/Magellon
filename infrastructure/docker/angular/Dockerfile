# Stage 1: Compile and Build angular codebase

# Use official node image as the base image
FROM node:latest as build

# Set the working directory
WORKDIR /app
ARG API_URL
# Install tree command
#RUN apt-get update && apt-get install -y tree

# Add the source code to app
COPY ./ /app/
COPY ./docker/nginx.conf /app/nginx/

# Debugging step to show directory tree
#RUN tree /app/

# If API_URL is provided, perform the replacement
RUN if [ -n "${API_URL}" ]; then \
      sed -i "s|http://backend:8000/web/|${API_URL}|g" /app/src/environments/environment.prod.ts; \
    fi

# Show content of file
#RUN cat /app/src/environments/environment.prod.ts
# Install all the dependencies
RUN npm install

# Generate the build of the application
RUN npm run build
#RUN npm run build --prod


# Stage 2: Serve app with nginx server

# Use official nginx image as the base image
#FROM nginx:alpine
FROM nginx:latest

# Copy the build output to replace the default nginx contents.
COPY --from=build /app/dist/magellon-app /usr/share/nginx/html
COPY --from=build /app/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Set the environment variables
ENV API_URL="${API_URL}"


# Expose port 80
#EXPOSE 4200 80
EXPOSE 80


#ENTRYPOINT ["nginx", "-g", "daemon off;"]