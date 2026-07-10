FROM node:20-alpine AS base

# Install dependencies only when needed
WORKDIR /app

# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
COPY package.json ./

RUN npm install

COPY . .

# In development mode Compose will bind mount the folder and override commands.
# This CMD serves as base.
CMD ["npm", "run", "dev"]
