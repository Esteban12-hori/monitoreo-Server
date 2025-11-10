FROM nginx:alpine

# Copiar configuración personalizada
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf

# Copiar frontend estático
COPY frontend /usr/share/nginx/html