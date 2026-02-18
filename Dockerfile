# Dockerfile
# Serves index.html via a lightweight nginx container for Azure App Service / Container Apps

FROM nginx:alpine

# Copy the generated web app
COPY index.html /usr/share/nginx/html/index.html

# Optional: custom nginx config for SPA-style routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
