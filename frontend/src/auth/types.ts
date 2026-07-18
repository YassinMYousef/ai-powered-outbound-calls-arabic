/**
 * Roles mirror the two consumers named in the requirements doc: the agent
 * desktop (chat widget) and the quality team (FCR dashboard). Extend this
 * once backend/app/data/auth.py's require_role() defines the real role set.
 */
export type Role = 'agent' | 'quality_manager'

export interface MockUser {
  name: string
  email: string
  role: Role
}
