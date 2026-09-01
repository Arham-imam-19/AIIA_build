FROM node:22-alpine

WORKDIR /app

# package.json first so the npm install layer is cached independently of source.
# The glob keeps this working whether or not a lockfile exists yet.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
