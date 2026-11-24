import { get } from './client'

// Mirrors HealthResponse in backend/app/schemas/common.py.
export interface Health {
  status: string
  app: string
  version: string
  environment: string
  database: string
  llm: string
}

export const getHealth = () => get<Health>('/health')
