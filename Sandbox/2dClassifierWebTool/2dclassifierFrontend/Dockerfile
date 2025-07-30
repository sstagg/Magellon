# Step 1: Build the React app in the latest Node.js environment
FROM node:latest AS build

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json for dependency installation
COPY package*.json ./
RUN npm install

# Copy the rest of your application code
COPY . .

ARG REACT_APP_BACKEND_URL

# Set the environment variable for the build
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Build the React application for production
RUN npm run build

# Step 2: Use Nginx to serve the build files
FROM nginx:alpine

# Copy the build files from the previous stage
COPY --from=build /app/build /usr/share/nginx/html


COPY default.conf /etc/nginx/conf.d/default.conf
# Expose port 80
EXPOSE 80

# Start Nginx server
CMD ["nginx", "-g", "daemon off;"]
