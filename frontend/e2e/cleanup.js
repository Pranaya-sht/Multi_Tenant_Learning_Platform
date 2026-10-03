import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

export default function cleanup() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  const python = path.resolve(
    root,
    process.platform === 'win32'
      ? '../backend/.venv/Scripts/python.exe'
      : '../backend/.venv/bin/python',
  )
  execFileSync(python, ['e2e/server.py', '--cleanup'], { cwd: root, stdio: 'inherit' })
}
