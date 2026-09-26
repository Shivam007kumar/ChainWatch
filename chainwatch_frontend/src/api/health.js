/**
 * api/health.js
 * Re-exports health functions from the central client.
 * Also exports getHealth() convenience alias used by InvestigationPage.
 */
export { API_BASE, getLiveness, getReadiness } from './client.js';
import { getReadiness } from './client.js';

/** Convenience alias — polls /health/ready and throws ApiError if not ready. */
export function getHealth() {
  return getReadiness();
}
