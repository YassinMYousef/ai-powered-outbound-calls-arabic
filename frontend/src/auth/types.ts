/**
 * Roles mirror backend/app/data/auth.py's ROLE_LEVELS (agent < quality_manager
 * < admin). The role always comes from the backend-issued token, never chosen
 * in the UI.
 */
export type Role = 'agent' | 'quality_manager' | 'admin'

export interface AuthUser {
  name: string
  email: string
  role: Role
}
