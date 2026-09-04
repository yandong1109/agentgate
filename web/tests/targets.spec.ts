// L3 组件测试：评测对象管理页（注册向导 / 列表 / 版本抽屉）
// API 层全部 mock（见《02-端到端验证方案》L3）——真实交互由 L2/L4 覆盖
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const probeMock = vi.fn()
const registerMock = vi.fn()
const listMock = vi.fn()
const detailMock = vi.fn()
const publishMock = vi.fn()

vi.mock('@/api/targets', () => ({
  targetsApi: {
    list: (...args: unknown[]) => listMock(...args),
    detail: (...args: unknown[]) => detailMock(...args),
    register: (...args: unknown[]) => registerMock(...args),
    probe: (...args: unknown[]) => probeMock(...args),
    probeTarget: (...args: unknown[]) => probeMock(...args),
    publishVersion: (...args: unknown[]) => publishMock(...args),
  },
}))

import TargetsPage from '@/views/targets/index.vue'
import RegisterWizard from '@/views/targets/components/RegisterWizard.vue'
import VersionDrawer from '@/views/targets/components/VersionDrawer.vue'
import type { TargetListItem } from '@/types/target'

const sampleTarget: TargetListItem = {
  id: 't-1',
  display_name: 'Order Agent',
  target_type: 'agent',
  adapter_type: 'http',
  external_target_id: 'order-agent',
  platform_id: 'registered',
  description: '订单智能体',
  capabilities: [{ name: 'create_order', kind: 'tool', description: '' }],
  status: 'ACTIVE',
  created_at: '2026-09-03T10:00:00Z',
  updated_at: '2026-09-03T10:00:00Z',
  version_count: 2,
  latest_version: {
    id: 'v-2',
    target_id: 't-1',
    version: 2,
    endpoint: 'http://127.0.0.1:9000/invoke',
    credential_ref: 'AGENTGATE_ORDER_KEY',
    invocation_config: { timeout_seconds: 30 },
    capabilities: [],
    content_sha256: 'a'.repeat(64),
    is_latest: true,
    published_at: '2026-09-03T11:00:00Z',
  },
}

beforeEach(() => {
  vi.clearAllMocks()
})

/** 取当前可见的向导表单（v-show 隐藏其余步骤） */
function visibleFormText(wrapper: ReturnType<typeof mount>): string {
  const forms = wrapper.findAll('.wizard-form')
  return forms
    .filter((form) => (form.element as HTMLElement).style.display !== 'none')
    .map((form) => form.text())
    .join('\n')
}

describe('评测对象列表页', () => {
  it('空数据渲染空态引导', async () => {
    listMock.mockResolvedValue([])
    const wrapper = mount(TargetsPage)
    await flushPromises()
    expect(listMock).toHaveBeenCalled()
    expect(wrapper.text()).toContain('暂无评测对象')
  })

  it('渲染对象行（名称/外部 ID/端点/凭证引用/最新版本）', async () => {
    listMock.mockResolvedValue([
      sampleTarget,
      { ...sampleTarget, id: 't-2', target_type: 'skill', display_name: 'Refund Skill' },
    ])
    const wrapper = mount(TargetsPage)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Order Agent')
    expect(text).toContain('order-agent')
    expect(text).toContain('http://127.0.0.1:9000/invoke')
    expect(text).toContain('AGENTGATE_ORDER_KEY')
    expect(text).toContain('Refund Skill')
  })
})

/** 推进向导到指定步骤（0 基），自动补齐前置必填项 */
async function advanceTo(wrapper: ReturnType<typeof mount>, step: number) {
  const next = () =>
    wrapper.findAll('button').find((b) => b.text() === '下一步')!
  if (step >= 1) {
    await wrapper
      .find('input[placeholder="例如：订单审批 Agent"]')
      .setValue('My Agent')
    await next().trigger('click')
    await flushPromises()
  }
  if (step >= 2) {
    await wrapper
      .find('input[placeholder="例如：http://127.0.0.1:8081/invoke"]')
      .setValue('http://127.0.0.1:9000/invoke')
    await next().trigger('click')
    await flushPromises()
  }
  if (step >= 3) {
    await next().trigger('click')
    await flushPromises()
  }
}

describe('注册向导', () => {
  it('步骤校验：名称必填、端点必须是 http(s) URL、合法则可推进', async () => {
    const wrapper = mount(RegisterWizard, { props: { visible: true } })
    await flushPromises()

    const next = () =>
      wrapper.findAll('button').find((b) => b.text() === '下一步')!

    // 空名称：停留在第 1 步
    await next().trigger('click')
    await flushPromises()
    expect(visibleFormText(wrapper)).toContain('展示名称')

    // 填写名称 → 进入第 2 步（端点/认证）
    await wrapper
      .find('input[placeholder="例如：订单审批 Agent"]')
      .setValue('My Agent')
    await next().trigger('click')
    await flushPromises()
    expect(visibleFormText(wrapper)).toContain('HTTP 端点')

    // 非法端点：拦截在第 2 步
    await wrapper
      .find('input[placeholder="例如：http://127.0.0.1:8081/invoke"]')
      .setValue('ftp://bad/invoke')
    await next().trigger('click')
    await flushPromises()
    expect(visibleFormText(wrapper)).toContain('HTTP 端点')

    // 合法端点 → 第 3 步（能力声明）
    await wrapper
      .find('input[placeholder="例如：http://127.0.0.1:8081/invoke"]')
      .setValue('http://127.0.0.1:9000/invoke')
    await next().trigger('click')
    await flushPromises()
    expect(visibleFormText(wrapper)).toContain('能力声明')
  })

  it('第 4 步：测试连接展示成功/失败结果', async () => {
    probeMock.mockResolvedValue({ ok: false, error_code: 'unauthorized', message: '401' })
    const wrapper = mount(RegisterWizard, { props: { visible: true } })
    await flushPromises()
    await advanceTo(wrapper, 3)
    expect(visibleFormText(wrapper)).toContain('测试连接')

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '测试连接')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('连接失败')
    expect(wrapper.text()).toContain('unauthorized')
  })

  it('确认注册：调用 register API 并抛出 registered 事件', async () => {
    registerMock.mockResolvedValue({
      target: { id: 't-9' },
      version: { version: 1 },
    })
    const wrapper = mount(RegisterWizard, { props: { visible: true } })
    await flushPromises()
    await advanceTo(wrapper, 3)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '确认注册')!
      .trigger('click')
    await flushPromises()

    expect(registerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        display_name: 'My Agent',
        endpoint: 'http://127.0.0.1:9000/invoke',
        adapter_type: 'http',
      }),
    )
    expect(wrapper.emitted('registered')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })
})

describe('版本抽屉', () => {
  it('加载并渲染版本列表（端点/哈希/最新标记/发布表单）', async () => {
    detailMock.mockResolvedValue({
      ...sampleTarget,
      versions: [
        sampleTarget.latest_version!,
        {
          ...sampleTarget.latest_version!,
          id: 'v-1',
          version: 1,
          endpoint: 'http://127.0.0.1:8000/invoke',
          credential_ref: null,
          is_latest: false,
          content_sha256: 'b'.repeat(64),
        },
      ],
    })
    const wrapper = mount(VersionDrawer, {
      props: { visible: true, targetId: 't-1' },
    })
    await flushPromises()

    expect(detailMock).toHaveBeenCalledWith('t-1')
    const text = wrapper.text()
    expect(text).toContain('Order Agent')
    expect(text).toContain('http://127.0.0.1:9000/invoke')
    expect(text).toContain('bbbbbbbbbbbb')
    expect(text).toContain('发布新版本')
    expect(text).toContain('不可变')
  })
})
