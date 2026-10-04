FROM node:22-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Start the Vite dev server (0.0.0.0:3000, see vite.config.mjs)
CMD ["npm", "start"]
