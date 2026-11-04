// Viewed-agent sensor (ADR-0008). Renders nothing: on every view switch it
// writes ~/.claude/claude-statusline/viewed-agent-<session_id>.json, which the
// Python statusline reads. This module, not scripts/, owns Claude Code's
// subagent path layout (ADR-0001). Every hook swallows its own errors.
import type { EngineInterface, Register } from 'claude-code'

const PRUNE_AFTER_MS = 7 * 24 * 60 * 60 * 1000
// Ids go into file names (and a `del` command line): a safe charset only.
const SAFE_ID = /^[A-Za-z0-9_-]+$/
const STATE_FILE = /^viewed-agent-[A-Za-z0-9_-]+\.json$/
// `<dir>/<stem>/subagents/agent-<id>.jsonl` → main is `<dir>/<stem>.jsonl`
const SUBAGENT_TRANSCRIPT = /^(.*)[\\/]subagents[\\/]agent-[^\\/]+\.jsonl$/

type Base = { transcript_path?: string; agent_transcript_path?: string }
type Paths = { jsonl: string; meta: string }

export const register: Register = on => {
  let transcriptPath: string | undefined
  // Last written `agentId|subagentPath`; undefined at load, so the first
  // render always writes and clears a state left by an earlier run.
  let lastWritten: string | undefined
  let queue: Promise<void> = Promise.resolve()

  // Main transcript path from any classic hook; a subagent's own path is
  // mapped back to its main transcript.
  const remember = (e: Base) => {
    for (const path of [e.transcript_path, e.agent_transcript_path]) {
      const main = path ? mainTranscript(path) : undefined
      if (main) {
        transcriptPath = main
        return
      }
    }
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

  // After a mid-session reload, the next subagent start or stop teaches the path.
  on('classic.SubagentStart', ($, e, next) => {
    try {
      remember(e)
    } catch {}
    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.SubagentStop', ($, e, next) => {
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
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, ($, e, next) => {
    try {
      const view = e.props.view
      const agentId = view?.agentId ?? ''
      // No view (older Claude Code), an unsafe id, or a subagent whose path is
      // not known yet (module reloaded mid-session): keep the previous state.
      const isKnown = view && (agentId === '' || (SAFE_ID.test(agentId) && transcriptPath))
      if (isKnown) {
        const paths = agentId && transcriptPath ? subagentPaths(transcriptPath, agentId) : undefined
        const key = `${agentId}|${paths?.jsonl ?? ''}`
        if (key !== lastWritten) {
          lastWritten = key
          queue = queue
            .then(() => writeState($, agentId, paths))
            .catch(() => {
              lastWritten = undefined
            })
        }
      }
    } catch {}
    return next(e)
  }).catch(($, e, next) => next(e))
}

function sepOf(path: string) {
  return path.includes('\\') ? '\\' : '/'
}

function mainTranscript(path: string) {
  const sub = SUBAGENT_TRANSCRIPT.exec(path)
  if (sub) return `${sub[1]}.jsonl`
  return /\.jsonl$/.test(path) ? path : undefined
}

// `<dir>/<stem>.jsonl` → `<dir>/<stem>/subagents/agent-<id>.{jsonl,meta.json}`
function subagentPaths(main: string, agentId: string): Paths {
  const sep = sepOf(main)
  const base = `${main.replace(/\.jsonl$/, '')}${sep}subagents${sep}agent-${agentId}`
  return { jsonl: `${base}.jsonl`, meta: `${base}.meta.json` }
}

// Python's expanduser: USERPROFILE on Windows, HOME elsewhere.
async function stateDir($: EngineInterface) {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME'))
  if (!home) return undefined
  const sep = sepOf(home)
  return `${home.replace(/[\\/]+$/, '')}${sep}.claude${sep}claude-statusline`
}

async function writeState($: EngineInterface, agentId: string, paths: Paths | undefined) {
  const dir = await stateDir($)
  const sessionId = await $.session.id()
  if (!dir || !SAFE_ID.test(sessionId)) return
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
  await $.fs.write(`${dir}${sepOf(dir)}viewed-agent-${sessionId}.json`, JSON.stringify(state))
}

async function prune($: EngineInterface) {
  const dir = await stateDir($)
  if (!dir || !(await $.fs.exists(dir))) return
  const sep = sepOf(dir)
  const cutoff = (await $.clock.now()) - PRUNE_AFTER_MS
  for (const entry of await $.fs.list(dir)) {
    if (entry.kind !== 'file' || !STATE_FILE.test(entry.name) || entry.mtimeMs >= cutoff) continue
    const path = `${dir}${sep}${entry.name}`
    // $.fs has no delete; remove through the host (Windows when the path uses `\`).
    await $.process.run(sep === '\\' ? ['cmd', '/c', 'del', '/q', path] : ['rm', '-f', path]).catch(() => undefined)
  }
}
