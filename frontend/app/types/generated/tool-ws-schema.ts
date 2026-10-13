/* Generated public tool event schemas. Run pnpm api:generate. */
export const toolWsDefinitions: Record<string, unknown> = {
  "ToolSnapshotEvent": {
    "additionalProperties": false,
    "properties": {
      "conversationId": {
        "format": "uuid",
        "title": "Conversationid",
        "type": "string"
      },
      "eventVersion": {
        "const": 1,
        "default": 1,
        "title": "Eventversion",
        "type": "integer"
      },
      "generationId": {
        "format": "uuid",
        "title": "Generationid",
        "type": "string"
      },
      "lastSequence": {
        "minimum": 0,
        "title": "Lastsequence",
        "type": "integer"
      },
      "runs": {
        "items": {
          "$ref": "#/$defs/ToolProjection"
        },
        "maxItems": 16,
        "title": "Runs",
        "type": "array"
      },
      "timestamp": {
        "format": "date-time",
        "title": "Timestamp",
        "type": "string"
      },
      "type": {
        "const": "tool.snapshot",
        "default": "tool.snapshot",
        "title": "Type",
        "type": "string"
      },
      "version": {
        "const": 1,
        "default": 1,
        "title": "Version",
        "type": "integer"
      }
    },
    "required": [
      "version",
      "eventVersion",
      "type",
      "conversationId",
      "generationId",
      "lastSequence",
      "timestamp",
      "runs"
    ],
    "title": "ToolSnapshotEvent",
    "type": "object"
  },
  "ToolProjection": {
    "additionalProperties": false,
    "properties": {
      "approval": {
        "anyOf": [
          {
            "$ref": "#/$defs/ToolApprovalProjection"
          },
          {
            "type": "null"
          }
        ],
        "default": null
      },
      "cancelRequested": {
        "title": "Cancelrequested",
        "type": "boolean"
      },
      "errorCode": {
        "anyOf": [
          {
            "enum": [
              "TOOL_UNAVAILABLE",
              "TOOL_FORBIDDEN",
              "TOOL_INPUT_INVALID",
              "TOOL_OUTPUT_INVALID",
              "TOOL_NOT_FOUND",
              "TOOL_CONFLICT",
              "TOOL_STATE_CONFLICT",
              "APPROVAL_REQUIRED",
              "APPROVAL_EXPIRED",
              "BUDGET_LIMIT",
              "TOOL_TIMEOUT",
              "TOOL_INTERRUPTED",
              "TOOL_CANCELLED",
              "PROVIDER_RATE_LIMIT",
              "PROVIDER_ERROR",
              "PROVIDER_OUTCOME_UNKNOWN"
            ],
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Errorcode"
      },
      "lastSequence": {
        "minimum": 0,
        "title": "Lastsequence",
        "type": "integer"
      },
      "result": {
        "anyOf": [
          {
            "$ref": "#/$defs/ToolResultReference"
          },
          {
            "type": "null"
          }
        ],
        "default": null
      },
      "runId": {
        "format": "uuid",
        "title": "Runid",
        "type": "string"
      },
      "state": {
        "enum": [
          "queued",
          "awaiting_approval",
          "running",
          "succeeded",
          "failed",
          "cancelled",
          "timed_out",
          "interrupted",
          "outcome_unknown"
        ],
        "title": "State",
        "type": "string"
      },
      "toolId": {
        "enum": [
          "web.search.v1",
          "web.fetch.v1"
        ],
        "title": "Toolid",
        "type": "string"
      },
      "updatedAt": {
        "format": "date-time",
        "title": "Updatedat",
        "type": "string"
      }
    },
    "required": [
      "runId",
      "toolId",
      "state",
      "lastSequence",
      "updatedAt",
      "cancelRequested",
      "approval",
      "result",
      "errorCode"
    ],
    "title": "ToolProjection",
    "type": "object"
  },
  "ToolResultReference": {
    "additionalProperties": false,
    "properties": {
      "resultVersion": {
        "const": 1,
        "default": 1,
        "title": "Resultversion",
        "type": "integer"
      },
      "sourceCount": {
        "anyOf": [
          {
            "maximum": 8,
            "minimum": 0,
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Sourcecount"
      }
    },
    "required": [
      "resultVersion",
      "sourceCount"
    ],
    "title": "ToolResultReference",
    "type": "object"
  },
  "ToolApprovalProjection": {
    "additionalProperties": false,
    "properties": {
      "approvalId": {
        "format": "uuid",
        "title": "Approvalid",
        "type": "string"
      },
      "expiresAt": {
        "format": "date-time",
        "title": "Expiresat",
        "type": "string"
      },
      "inputDigest": {
        "pattern": "^[0-9a-f]{64}$",
        "title": "Inputdigest",
        "type": "string"
      },
      "state": {
        "enum": [
          "pending",
          "approved",
          "denied",
          "expired"
        ],
        "title": "State",
        "type": "string"
      }
    },
    "required": [
      "approvalId",
      "inputDigest",
      "state",
      "expiresAt"
    ],
    "title": "ToolApprovalProjection",
    "type": "object"
  },
  "ToolEvent": {
    "additionalProperties": false,
    "properties": {
      "conversationId": {
        "format": "uuid",
        "title": "Conversationid",
        "type": "string"
      },
      "eventVersion": {
        "const": 1,
        "default": 1,
        "title": "Eventversion",
        "type": "integer"
      },
      "generationId": {
        "format": "uuid",
        "title": "Generationid",
        "type": "string"
      },
      "payload": {
        "$ref": "#/$defs/ToolProjection"
      },
      "runId": {
        "format": "uuid",
        "title": "Runid",
        "type": "string"
      },
      "seq": {
        "minimum": 1,
        "title": "Seq",
        "type": "integer"
      },
      "timestamp": {
        "format": "date-time",
        "title": "Timestamp",
        "type": "string"
      },
      "type": {
        "enum": [
          "tool.started",
          "tool.progress",
          "tool.result",
          "tool.approval_required",
          "tool.completed",
          "tool.failed",
          "tool.cancelled",
          "tool.timed_out"
        ],
        "title": "Type",
        "type": "string"
      },
      "version": {
        "const": 1,
        "default": 1,
        "title": "Version",
        "type": "integer"
      }
    },
    "required": [
      "version",
      "eventVersion",
      "type",
      "conversationId",
      "generationId",
      "runId",
      "seq",
      "timestamp",
      "payload"
    ],
    "title": "ToolEvent",
    "type": "object"
  }
}
