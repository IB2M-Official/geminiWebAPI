#!/usr/bin/env node
/**
 * One-time Login Helper for Gemini Web (Node.js / Playwright)
 */
const { runLogin } = require('./index');

runLogin().catch((err) => {
  console.error('Login error:', err);
  process.exit(1);
});
