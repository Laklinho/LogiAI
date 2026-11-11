FROM nginx:alpine

# Contexte de build = racine du projet : les chemins commencent par web/ et nginx/
COPY web/index.html /usr/share/nginx/html/index.html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
