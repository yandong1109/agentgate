import { defineConfig, devices } from '@playwright/test'
import os from 'os'
import path from 'path'

// E2E 隔离：临时 DB + 独立端口（18000 后端 / 15173 前端 / 18081 假 Agent），不撞开发后端
const testDatabase = path.join(os.tmpdir(), `agentgate-playwright-${process.pid}.db`)

// Python 解释器可注入（本地 venv：AGENTGATE_PYTHON=../.venv/bin/python npm run test:e2e）
// 含路径分隔符时解析为绝对路径，避免不同 webServer 的 cwd 影响相对路径
const rawPython = process.env.AGENTGATE_PYTHON || 'python3'
const pythonBin = rawPython.includes('/') ? path.resolve(rawPython) : rawPython

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  webServer: [
    {
      command: `${pythonBin} -m uvicorn agentgate.server.application:app --host 127.0.0.1 --port 18000`,
      port: 18000,
      reuseExistingServer: false,
      env: { ...process.env, AGENTGATE_DB: testDatabase, PYTHONPATH: '../src' },
    },
    {
      // 假 Agent：模拟真实被测对象（行为可编程 + OTLP trace 回传），见 tests/fake_agent_server.py
      command: `${pythonBin} -m tests.fake_agent_server --port 18081`,
      cwd: '..',
      port: 18081,
      reuseExistingServer: false,
      env: { ...process.env, AGENTGATE_DB: testDatabase, PYTHONPATH: 'src' },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 15173',
      port: 15173,
      reuseExistingServer: false,
      env: { ...process.env, AGENTGATE_API_TARGET: 'http://127.0.0.1:18000' },
    },
  ],
  use: {
    baseURL: 'http://127.0.0.1:15173',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
  ],
})
