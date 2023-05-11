# Stage 1: Compile and Build angular codebase

# Use official node image as the base image
FROM node:latest as build

# Set the working directory
WORKDIR /app

# Add the source code to app
COPY ./ /app/
COPY ./docker/nginx.conf /app/nginx/
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
ENV API_URL="http://magellon-core-service01:8000/web/"


# Expose port 80
#EXPOSE 4200 80
EXPOSE 80


#ENTRYPOINT ["nginx", "-g", "daemon off;"]