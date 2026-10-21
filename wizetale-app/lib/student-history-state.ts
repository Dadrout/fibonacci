export type StoryHistoryRecord = {
  id: string
  task_id: string
  title: string
  subject: string
  topic: string
  created_at: string
  result?: { video_url?: string; recap?: string }
}

export type StoryHistoryState = {
  stories: StoryHistoryRecord[]
  busy: boolean
  initialError: string | null
  hasMore: boolean
  loadingMore: boolean
  moreError: string | null
  retryOffset: number | null
}

export const initialStoryHistoryState: StoryHistoryState = {
  stories: [],
  busy: true,
  initialError: null,
  hasMore: false,
  loadingMore: false,
  moreError: null,
  retryOffset: null,
}

export type StoryHistoryAction =
  | { type: 'initialStarted' }
  | { type: 'initialSucceeded'; stories: StoryHistoryRecord[]; hasMore: boolean }
  | { type: 'initialFailed'; error: string }
  | { type: 'appendStarted' }
  | { type: 'appendSucceeded'; stories: StoryHistoryRecord[]; hasMore: boolean }
  | { type: 'appendFailed'; error: string; offset: number }

export function reduceStoryHistory(
  state: StoryHistoryState,
  action: StoryHistoryAction,
): StoryHistoryState {
  switch (action.type) {
    case 'initialStarted':
      return { ...state, busy: true, initialError: null }
    case 'initialSucceeded':
      return {
        ...state,
        stories: action.stories,
        busy: false,
        initialError: null,
        hasMore: action.hasMore,
        moreError: null,
        retryOffset: null,
      }
    case 'initialFailed':
      return { ...state, busy: false, initialError: action.error }
    case 'appendStarted':
      return { ...state, loadingMore: true, moreError: null }
    case 'appendSucceeded':
      {
        const knownIds = new Set(state.stories.map((story) => story.id))
        const newStories = action.stories.filter((story) => {
          if (knownIds.has(story.id)) return false
          knownIds.add(story.id)
          return true
        })
      return {
        ...state,
        stories: [...state.stories, ...newStories],
        loadingMore: false,
        hasMore: action.hasMore,
        moreError: null,
        retryOffset: null,
      }
      }
    case 'appendFailed':
      return {
        ...state,
        loadingMore: false,
        moreError: action.error,
        retryOffset: action.offset,
      }
  }
}
