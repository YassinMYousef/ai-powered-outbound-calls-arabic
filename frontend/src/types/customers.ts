/** Mirrors backend/app/api/customers.py's response shapes. */
export interface Customer {
  id: number
  name: string
  phone: string
  notes: string | null
  created_at: string
}

export interface CustomerCallHistoryEntry {
  id: number
  ticket_id: string | null
  status: string
  outcome: string | null
  created_at: string
}

export interface CustomerDetail extends Customer {
  call_history: CustomerCallHistoryEntry[]
}

export interface FlagResponse {
  id: number
  customer_id: number
  customer_phone: string
  ticket_id: string | null
  status: string
}
