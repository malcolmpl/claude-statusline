import { expect, mock, test } from 'claude-code/testing'

const MAIN = 'C:\\Users\\u\\.claude\\projects\\p\\sess.jsonl'
const SUBAGENTS = 'C:\\Users\\u\\.claude\\projects\\p\\sess\\subagents\\'
const STATE = 'C:\\Users\\u\\.claude\\claude-statusline\\viewed-agent-sess.json'

const band = (agentId?: string) =>
  ({
    plugin: 'claude-statusline',
    surface: 'terminal',
    component: 'AbovePrompt',
    props: {
      hasSurvey: false,
      isWorking: false,
      maxRows: 10,
      bodyColumns: 80,
      scroll: { offset: 0, bodyRows: 10 },
      view: agentId ? { agentId } : {},
    },
  }) as const

test('a view switch writes the state file; an unchanged view does not', async ($, on) => {
  mock.env(on, { USERPROFILE: 'C:\\Users\\u' })
  const writes: { path: string; text: string }[] = []
  on('session.id', () => ({ value: 'sess' }))
  on('fs.write', (_, e) => {
    writes.push(e)
    return { value: undefined }
  })
  on('fs.read', (_, e) => {
    expect(e.path).toBe(`${SUBAGENTS}agent-a1.meta.json`)
    return { value: JSON.stringify({ agentType: 'Explore', model: 'sonnet', effort: 'low' }) }
  })
  on('classic.UserPromptSubmit', () => ({}))
  // Stands for the engine's own drawing beneath the band.
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  await $.classic.UserPromptSubmit({ prompt: 'hi', session_id: 'sess', transcript_path: MAIN })

  let ui = await $.ui.mount(band('a1'))
  await ui.unmount()
  ui = await $.ui.mount(band('a1'))
  await ui.unmount()
  expect(writes.length).toBe(1)
  expect(writes[0]?.path).toBe(STATE)
  expect(JSON.parse(writes[0]?.text ?? '')).toEqual({
    agentId: 'a1',
    transcriptPath: `${SUBAGENTS}agent-a1.jsonl`,
    agentType: 'Explore',
    model: 'sonnet',
    effort: 'low',
  })

  ui = await $.ui.mount(band())
  await ui.unmount()
  expect(writes.length).toBe(2)
  expect(JSON.parse(writes[1]?.text ?? '')).toEqual({ agentId: '', transcriptPath: '' })
})

test('session start deletes state files older than 7 days, and nothing else', async ($, on) => {
  mock.env(on, { USERPROFILE: 'C:\\Users\\u', OS: 'Windows_NT' })
  mock.clock(on, { now: 10 * 86_400_000 })
  const runs: string[][] = []
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('fs.exists', () => ({ value: true }))
  on('fs.list', () => ({
    value: [
      { name: 'viewed-agent-old.json', kind: 'file', size: 1, mtimeMs: 1 * 86_400_000, isLink: false },
      { name: 'viewed-agent-new.json', kind: 'file', size: 1, mtimeMs: 9 * 86_400_000, isLink: false },
      { name: 'other.json', kind: 'file', size: 1, mtimeMs: 1, isLink: false },
    ],
  }))
  on('process.run', (_, e) => {
    runs.push([...e.argv])
    return { value: { exitCode: 0, stdout: '', stderr: '' } }
  })

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })

  expect(runs).toEqual([['cmd', '/c', 'del', '/q', 'C:\\Users\\u\\.claude\\claude-statusline\\viewed-agent-old.json']])
})
