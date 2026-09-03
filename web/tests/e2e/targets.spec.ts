import { expect, test } from '@playwright/test'

// 评测对象管理 E2E（L4）：真实浏览器 + 真实后端 + 假 Agent（18081，OTLP 回传共享 DB）
// 见《02-端到端验证方案》§3 L4。旅程与 demo.spec.ts 完全隔离（独立注册名）。

const FAKE_ENDPOINT = 'http://127.0.0.1:18081/invoke'

test('registers a target through the wizard and runs a real evaluation against it', async ({ page }) => {
  // ── 注册向导：基本信息 → 端点/认证 → 能力声明 → 测试并注册 ──
  await page.goto('/targets')
  await expect(page.getByRole('heading', { name: '评测对象' })).toBeVisible()
  await page.getByRole('button', { name: '注册评测对象' }).first().click()

  const dialog = page.getByRole('dialog')
  await dialog.getByPlaceholder('例如：订单审批 Agent').fill('E2E Order Agent')
  await dialog.getByRole('button', { name: '下一步' }).click()

  await dialog.getByPlaceholder('例如：http://127.0.0.1:8081/invoke').fill(FAKE_ENDPOINT)
  await dialog.getByRole('button', { name: '下一步' }).click()

  // 能力声明：添加一条
  await dialog.getByRole('button', { name: '+ 添加能力' }).click()
  await dialog.getByPlaceholder('能力名，如 loan_approval').fill('process_order')
  await dialog.getByRole('button', { name: '下一步' }).click()

  // 测试连接（真实调用假 Agent）
  await dialog.getByRole('button', { name: '测试连接' }).click()
  await expect(dialog.getByText('连接成功')).toBeVisible()

  await dialog.getByRole('button', { name: '确认注册' }).click()
  await expect(page.getByText('注册成功')).toBeVisible()

  // 列表可见新对象（限定表格行，避免与残留的向导弹窗文本冲突）
  const row = page.getByRole('row').filter({ hasText: 'E2E Order Agent' })
  await expect(row).toBeVisible()
  await expect(row).toContainText('e2e-order-agent')
  await expect(row).toContainText(FAKE_ENDPOINT)

  // ── 发起评测：注册对象出现在 Agent 选择器中，跑真实闭环 ──
  await page.goto('/runs')
  await page.getByTestId('agent-select').click()
  await page.getByRole('option', { name: /E2E Order Agent · v1/ }).click()
  await page.getByRole('button', { name: /运行评估/ }).click()

  // 结果报告渲染（假 Agent 已回传 OTLP，Run 完成）
  await expect(page.getByRole('heading', { name: '结果报告' })).toBeVisible({
    timeout: 60_000,
  })
})

test('wizard probe reports a categorized, redacted error for a dead endpoint', async ({ page }) => {
  await page.goto('/targets')
  await page.getByRole('button', { name: '注册评测对象' }).first().click()

  const dialog = page.getByRole('dialog')
  await dialog.getByPlaceholder('例如：订单审批 Agent').fill('Dead Endpoint Agent')
  await dialog.getByRole('button', { name: '下一步' }).click()

  // 死端口 + 密钥查询参数（验证脱敏：哨兵密钥不得回显）
  await dialog
    .getByPlaceholder('例如：http://127.0.0.1:8081/invoke')
    .fill('http://127.0.0.1:59999/invoke?api_key=sentinel-e2e-secret')
  await dialog.getByRole('button', { name: '下一步' }).click()
  await dialog.getByRole('button', { name: '下一步' }).click()
  await dialog.getByRole('button', { name: '测试连接' }).click()

  const errorAlert = dialog.locator('.el-alert--error')
  await expect(dialog.getByText('连接失败 [timeout]')).toBeVisible()
  // 安全红线：错误信息（告警标题+描述）不得包含密钥明文（端点输入框的自身回显除外）
  await expect(errorAlert).not.toContainText('sentinel-e2e-secret')
})

test('publishes a new version in the version drawer and latest moves', async ({ page }) => {
  // 先注册一个对象（复用向导，跳过探测）
  await page.goto('/targets')
  await page.getByRole('button', { name: '注册评测对象' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByPlaceholder('例如：订单审批 Agent').fill('E2E Versioned Agent')
  await dialog.getByRole('button', { name: '下一步' }).click()
  await dialog.getByPlaceholder('例如：http://127.0.0.1:8081/invoke').fill(FAKE_ENDPOINT)
  await dialog.getByRole('button', { name: '下一步' }).click()
  await dialog.getByRole('button', { name: '下一步' }).click()
  await dialog.getByRole('button', { name: '确认注册' }).click()
  await expect(page.getByText('注册成功')).toBeVisible()

  // 打开版本管理抽屉
  const row = page.getByRole('row').filter({ hasText: 'E2E Versioned Agent' })
  await row.getByRole('button', { name: '版本管理' }).click()

  const drawer = page.locator('.el-drawer')
  await expect(drawer.getByText('已发布版本（不可变）')).toBeVisible()
  await expect(drawer.getByText('v1 · 最新')).toBeVisible()

  // 发布 v2：新端点
  await drawer.locator('.publish-form input').first().fill(FAKE_ENDPOINT)
  await drawer.getByRole('button', { name: '发布版本' }).click()
  await expect(page.getByText('已发布 v2')).toBeVisible()

  // is_latest 迁移到 v2
  await expect(drawer.getByText('v2 · 最新')).toBeVisible()

  // /runs 的 Agent 选择器两个版本都可选（rerun 对比能力的基础）
  await page.goto('/runs')
  await page.getByTestId('agent-select').click()
  await expect(page.getByRole('option', { name: /E2E Versioned Agent · v2/ })).toBeVisible()
})
