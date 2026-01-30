# Pre-built site - copy the public folder directly
FROM nginx:alpine

# Copy pre-built site (run `zola build` before docker build)
COPY public/ /usr/share/nginx/html/

# Copy nginx config for proper WASM MIME type
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
