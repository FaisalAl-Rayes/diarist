import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Minimal production server bundle for the Docker image (see Dockerfile).
  output: "standalone",
  // This app is a live dashboard (job polling, uploads); every page depends
  // on request-time data from the backend, so there is nothing worth
  // precomputing with Cache Components/PPR.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
