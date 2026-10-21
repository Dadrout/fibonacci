import test from 'node:test'
import assert from 'node:assert/strict'
import { sourceLabel, sourceOpenUrl, safeSourceUrl } from '../components/brain/source-viewer-helpers.ts'
import { copyText } from '../lib/copy.ts'
import { formatTimestamp, youtubeEmbedUrl } from '../lib/brain-api-helpers.ts'

const source = { item_id: 'source', chunk_id: 'chunk', item_kind: 'photo', item_title: 'Slide photo', course_id: null, anchor: { kind: 'slide', slide: 7 }, quote: 'Variance changes with x.', captured_at: '2026-10-03T12:00:00Z', thumbnail_url: null, open_url: null, youtube_id: null, media_url: '/api/v1/brain/media/signed?token=abc' }

test('photo citations retain slide and capture date in all three languages', () => {
  assert.equal(sourceLabel(source, key => key, 'en', ''), 'Slide 7 · photo from Oct 3')
  for (const locale of ['ru', 'kk']) {
    const label = sourceLabel(source, key => copyText(key, locale), locale, '')
    assert.match(label, /7/)
    assert.match(label, /3/)
    assert.doesNotMatch(label, /photo from|\{date\}|\{slide\}/)
  }
  assert.equal(sourceLabel({ ...source, anchor: { kind: 'slide', slide: null } }, key => key, 'en', ''), 'Photo from Oct 3')
})

test('PDF opens the cited page without losing the signed query, and unsafe links are omitted', () => {
  assert.equal(sourceOpenUrl({ ...source, anchor: { kind: 'page', page: 4 }, media_url: source.media_url + '#page=1' }), '/api/v1/brain/media/signed?token=abc#page=4')
  assert.equal(sourceLabel({ ...source, item_kind: 'pdf', anchor: { kind: 'page', page: 4 } }, key => key, 'en', ''), 'Page 4 · PDF')
  for (const url of ['javascript:alert(1)', '//evil.test', '/\\evil.test', 'data:text/html,hi']) assert.equal(safeSourceUrl(url), null)
  assert.equal(sourceOpenUrl({ ...source, media_url: null, open_url: 'https://example.com/lecture#variance' }), 'https://example.com/lecture#variance')
})

test('timestamp citation and embedded player agree on the exact 14:32–15:10 window', () => {
  const video = { ...source, item_kind: 'youtube', youtube_id: '2xcUup_-K6c', anchor: { kind: 'timestamp', start_sec: 872, end_sec: 910 } }
  const window = `${formatTimestamp(video.anchor.start_sec)}–${formatTimestamp(video.anchor.end_sec)}`
  assert.equal(sourceLabel(video, key => key, 'en', window), '14:32–15:10 · video')
  const embed = new URL(youtubeEmbedUrl(video.youtube_id, 872, 910))
  assert.equal(embed.searchParams.get('start'), '872')
  assert.equal(embed.searchParams.get('end'), '910')
  assert.equal(sourceLabel({ ...video, youtube_id: null, item_kind: 'audio' }, key => key, 'en', window), '14:32–15:10 · audio')
  assert.equal(sourceLabel({ ...source, anchor: { kind: 'paragraph', paragraph: 2 } }, key => key, 'en', ''), 'Paragraph 2 · text')
  assert.equal(sourceLabel({ ...source, anchor: { kind: 'section', heading: 'Variance' } }, key => key, 'en', ''), 'Variance · web page')
})
