FROM node:18-alpine

WORKDIR /app

COPY package.json .
RUN npm install express http-proxy-middleware

COPY . .

EXPOSE 8090

CMD ["node", "proxy.js"]