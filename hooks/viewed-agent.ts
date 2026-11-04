// Viewed-agent sensor (ADR-0008). Renders nothing: on every view switch it
// writes ~/.claude/claude-statusline/viewed-agent-<session_id>.json, which the
// Python statusline reads. This module, not scripts/, owns Claude Code's
// subagent path layout (ADR-0001). Every hook swallows its own errors.
import type { EngineInterface, Register } from 'claude-code'

const PRUNE_AFTER_MS = 7 * 24 * 60 * 60 * 1000
const STATE_FILE = /^viewed-agent-.+\.json$/

type Base = { session_id?: string; transcript_path?: string }

export const register: Register = on => {
  let transcriptPath: string | undefined
  let hookSessionId: string | undefined
  // Last written `agentId|subagentPath`; undefined at load, so the first
  // render always writes and clears a state left by an earlier run.
  let lastWritten: string | undefined
  let queue: Promise<void> = Promise.resolve()

  const remember = (e: Base) => {
    if (e.transcript_path) transcriptPath = e.transcript_path
    if (e.session_id) hookSessionId = e.session_id
  }

  on('classic.SessionStart', ($, e, next) => {
    try {
      remember(e)
    } catch {}
    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.UserPromptSubmit', ($, e, next) => {
    try {
      remember(e)
    } catch {}
    return next(e)
  }).catch(($, e, next) => next(e))

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    try {
      await prune($)
    } catch {}
    return started
  })

  on('ui.render', { component: 'AbovePrompt' }, ($, e, next) => {
    try {
      const view = e.props.view
      if (view) {
        const agentId = view.agentId ?? ''
        const paths = agentId && transcriptPath ? subagentPaths(transcriptPath, agentId) : undefined
        const key = `${agentId}|${paths?.jsonl ?? ''}`
        if (key !== lastWritten) {
          lastWritten = key
          queue = queue
            .then(() => writeState($, agentId, paths, hookSessionId))
            .catch(() => {
              lastWritten = undefined
            })
        }
      }
    } catch {}
    return next(e)
  })
}

// `<dir>/<stem>.jsonl` → `<dir>/<stem>/subagents/agent-<id>.{jsonl,meta.json}`
function subagentPaths(mainTranscript: string, agentId: string) {
  const cut = Math.max(mainTranscript.lastIndexOf('/'), mainTranscript.lastIndexOf('\\'))
  const sep = cut >= 0 ? mainTranscript[cut] : '/'
  const dir = mainTranscript.slice(0, cut + 1)
  const stem = mainTranscript.slice(cut + 1).replace(/\.jsonl$/, '')
  const base = `${dir}${stem}${sep}subagents${sep}agent-${agentId}`
  return { jsonl: `${base}.jsonl`, meta: `${base}.meta.json` }
}

// Python's expanduser: USERPROFILE on Windows, HOME elsewhere.
async function stateDir($: EngineInterface) {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME'))
  if (!home) return undefined
  const sep = home.includes('\\') ? '\\' : '/'
  return `${home.replace(/[\\/]+$/, '')}${sep}.claude${sep}claude-statusline`
}

async function writeState(
  $: EngineInterface,
  agentId: string,
  paths: { jsonl: string; meta: string } | undefined,
  hookSessionId: string | undefined,
) {
  const dir = await stateDir($)
  if (!dir) return
  const sep = dir.includes('\\') ? '\\' : '/'
  const state: Record<string, unknown> = { agentId: paths ? agentId : '', transcriptPath: paths?.jsonl ?? '' }
  if (paths) {
    try {
      const meta = JSON.parse(await $.fs.read(paths.meta))
      if (meta && typeof meta === 'object') {
        state.agentType = meta.agentType ?? null
        state.model = meta.model ?? null
        state.effort = meta.effort ?? null
      }
    } catch {}
  }
  const text = JSON.stringify(state)
  // The statusline keys by stdin `session_id`; write under the hook's id too
  // if it ever differs from $.session.id().
  const ids = new Set([await $.session.id(), hookSessionId].filter((x): x is string => !!x))
  for (const id of ids) {
    await $.fs.write(`${dir}${sep}viewed-agent-${id}.json`, text)
  }
}

async function prune($: EngineInterface) {
  const dir = await stateDir($)
  if (!dir || !(await $.fs.exists(dir))) return
  const sep = dir.includes('\\') ? '\\' : '/'
  const cutoff = (await $.clock.now()) - PRUNE_AFTER_MS
  const isWindows = (await $.env.get('OS')) === 'Windows_NT'
  for (const entry of await $.fs.list(dir)) {
    if (entry.kind !== 'file' || !STATE_FILE.test(entry.name) || entry.mtimeMs >= cutoff) continue
    const path = `${dir}${sep}${entry.name}`
    // $.fs has no delete; remove through the host.
    await $.process.run(isWindows ? ['cmd', '/c', 'del', '/q', path] : ['rm', '-f', path]).catch(() => undefined)
  }
}
