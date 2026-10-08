/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */
export type Code = string
export type Message = string
export type RequestId = string
export type Service = "noris-ai"
export type Status = "ok"
export type Version = string
export type Status1 = "ready"

export interface ApiSchemas {
  ErrorDetail: ErrorDetail
  ErrorResponse: ErrorResponse
  HealthResponse: HealthResponse
  ReadinessResponse: ReadinessResponse
}
export interface ErrorDetail {
  code: Code
  message: Message
  request_id: RequestId
}
export interface ErrorResponse {
  error: ErrorDetail
}
export interface HealthResponse {
  service?: Service
  status?: Status
  version: Version
}
export interface ReadinessResponse {
  status?: Status1
}

export interface ApiPaths {
  "/api/v1/health/live": {
    get: { responses: {
      200: ApiSchemas["HealthResponse"]
    } }
  }
  "/api/v1/health/ready": {
    get: { responses: {
      200: ApiSchemas["ReadinessResponse"]
      503: ApiSchemas["ErrorResponse"]
    } }
  }
}
