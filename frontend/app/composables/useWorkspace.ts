import { inject } from 'vue'
import type { InjectionKey, Ref } from 'vue'
import type { useChat } from './useChat'
import type { useModelSelection } from './useModelSelection'

export interface Workspace {
  chat: ReturnType<typeof useChat>
  selection: ReturnType<typeof useModelSelection>
  mode: 'mock' | 'real' | 'websocket'
  importAvailable: Ref<boolean>
}
export const workspaceKey: InjectionKey<Workspace> = Symbol('chat-workspace')
export function useWorkspace(): Workspace {
  const workspace = inject(workspaceKey)
  if (!workspace) throw new Error('Settings require the existing chat workspace')
  return workspace
}
