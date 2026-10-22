export function learnerStorageKey(kind: 'draft' | 'draft-shelf' | 'job', userId: string): string {
  if (!userId) throw new Error('A signed-in learner is required.')
  return `fibonacci-current-${kind}:${userId}`
}
