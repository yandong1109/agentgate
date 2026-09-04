import { defineConfig, devices } from '@playwright/test'
import os from 'os'
import path from 'path'

// E2E 隔离：临时 DB + 独立端口（18000 后端 / 15173 前端 / 18081 假 Agent），不撞开发后端
const testDatabase = path.join(os.tmpdir(), `agentgate-playwright-${process.pid}.db`)
// trace-sdk 事件目录（假 Agent 写、后端拉取——trace-sdk-integration-plan 新通道）
const sdkEventRoot = path.join(os.tmpdir(), `agentgate-playwright-sdk-${process.pid}`)

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
      env: {
        ...process.env,
        AGENTGATE_DB: testDatabase,
        PYTHONPATH: '../src',
        AGENTGATE_TRACE_SDK_FILE_ROOT: sdkEventRoot,
      },
    },
    {
      // 假 Agent：模拟真实被测对象（行为可编程 + 遥测回传），见 tests/fake_agent_server.py
      // 设置 AGENTGATE_TRACE_SDK_FILE_ROOT 即走 trace-sdk 桥接模式（事件 JSONL）
      command: `${pythonBin} -m tests.fake_agent_server --port 18081`,
      cwd: '..',
      port: 18081,
      reuseExistingServer: false,
      env: {
        ...process.env,
        AGENTGATE_DB: testDatabase,
        PYTHONPATH: 'src',
        AGENTGATE_TRACE_SDK_FILE_ROOT: sdkEventRoot,
      },
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
