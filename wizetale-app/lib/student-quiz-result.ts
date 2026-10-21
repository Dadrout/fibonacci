export type SavedQuizResult = {
  answers: Record<string, string>
  score: number
  total: number
}

export function parseQuizResult(
  payload: unknown,
  optionIds: readonly (readonly string[])[],
): SavedQuizResult | null {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('The saved quiz result could not be read.')
  }

  const envelope = payload as Record<string, unknown>
  const candidate = Object.prototype.hasOwnProperty.call(envelope, 'result')
    ? envelope.result
    : envelope
  if (candidate === null) return null
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
    throw new Error('The saved quiz result could not be read.')
  }

  const result = candidate as Record<string, unknown>
  const expectedKeys = optionIds.map((_, index) => String(index + 1))
  const answers = result.answers
  if (
    optionIds.length === 0 ||
    !answers || typeof answers !== 'object' || Array.isArray(answers) ||
    result.total !== optionIds.length ||
    !Number.isInteger(result.score) || Number(result.score) < 0 || Number(result.score) > optionIds.length
  ) {
    throw new Error('The saved quiz result could not be read.')
  }

  const answerRecord = answers as Record<string, unknown>
  if (Object.keys(answerRecord).length !== expectedKeys.length || expectedKeys.some((key, index) => {
    const answer = answerRecord[key]
    return typeof answer !== 'string' || !optionIds[index].includes(answer)
  })) {
    throw new Error('The saved quiz result could not be read.')
  }

  return {
    answers: answerRecord as Record<string, string>,
    score: Number(result.score),
    total: optionIds.length,
  }
}
