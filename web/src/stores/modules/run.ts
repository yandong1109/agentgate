// Run 域状态（评估配置选择）
// 对齐 App.vue L12-L14：selectedVersion/selectedDataset/selectedEvaluators
import { defineStore } from 'pinia'

interface RunConfigState {
  selectedVersion: string
  selectedDataset: string
  selectedEvaluators: string[]
  loading: boolean
}

export const useRunStore = defineStore('run', {
  state: (): RunConfigState => ({
    selectedVersion: 'loan-agent-v2-fixed',
    selectedDataset: 'loan-risk-policy',
    selectedEvaluators: [],
    loading: false,
  }),
  actions: {
    setVersion(version: string) {
      this.selectedVersion = version
    },
    // 版本列表加载后校正默认选择：当前值失效时回落到 is_latest 项
    ensureVersionExists(versions: { id: string; is_latest: boolean }[]) {
      if (versions.some((item) => item.id === this.selectedVersion)) return
      this.selectedVersion =
        versions.find((item) => item.is_latest)?.id ?? versions[0]?.id ?? this.selectedVersion
    },
    setDataset(datasetId: string) {
      this.selectedDataset = datasetId
    },
    setEvaluators(ids: string[]) {
      this.selectedEvaluators = ids
    },
    resetEvaluatorsIfEmpty(evaluatorIds: string[]) {
      if (this.selectedEvaluators.length === 0) {
        this.selectedEvaluators = [...evaluatorIds]
      }
    },
  },
})
