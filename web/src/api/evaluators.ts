// Evaluator 域 API
import { http } from '@/utils/request'
import type { EvaluatorOption } from '@/types/evaluator'

export const evaluatorsApi = {
  evaluators: () => http.get<EvaluatorOption[]>('/api/evaluators'),
}

export default evaluatorsApi
