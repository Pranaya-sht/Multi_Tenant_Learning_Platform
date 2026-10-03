import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

const windows = process.platform === 'win32'
const python = path.resolve(
  windows ? '../backend/.venv/Scripts/python.exe' : '../backend/.venv/bin/python',
)

export default defineConfig({
  testDir: './e2e',
  testMatch: '*.spec.js',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: 'list',
  globalTeardown: './e2e/cleanup.js',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://127.0.0.1:4173',
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${python}" e2e/server.py`,
      url: 'http://127.0.0.1:8001/api/v1/health/ready',
      timeout: 60000,
      reuseExistingServer: false,
    },
    {
      command: `${windows ? 'npm.cmd' : 'npm'} run dev -- --host 127.0.0.1 --port 4173`,
      url: 'http://127.0.0.1:4173',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8001' },
      timeout: 30000,
      reuseExistingServer: false,
    },
  ],
})
