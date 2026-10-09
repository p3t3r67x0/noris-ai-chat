// @ts-check
import { spawnSync } from 'node:child_process'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript-lite'

/** @typedef {import('json-schema-to-typescript-lite').JSONSchema} JSONSchema */
/** @typedef {{$ref?: string, oneOf?: ContractSchema[], anyOf?: ContractSchema[]}} ContractSchema */
/** @typedef {{in: string, schema?: {type?: string}}} Parameter */
/** @typedef {{operationId: string, parameters?: Parameter[], requestBody?: {content: Record<string, {schema: ContractSchema}>}, responses: Record<string, {content?: Record<string, {schema: ContractSchema}>}>}} Operation */
/** @typedef {{components: {schemas: Record<string, JSONSchema>}, paths: Record<string, Record<string, Operation>>}} ApiDocument */

const root = fileURLToPath(new URL('../', import.meta.url))
const check = process.argv.includes('--check')
const temporary = await mkdtemp(join(tmpdir(), 'noris-api-'))

try {
  const schemaPath = join(temporary, 'openapi.json')
  const result = spawnSync('uv', ['run', '--locked', 'python', 'scripts/export_openapi.py', schemaPath], {
    cwd: join(root, 'backend'), encoding: 'utf8',
  })
  if (result.status !== 0) throw new Error(result.stderr || 'OpenAPI export failed')
  const contract = await readFile(schemaPath, 'utf8')
  /** @type {ApiDocument} */
  const document = JSON.parse(contract)
  /** @type {Record<string, JSONSchema>} */
  const schemas = JSON.parse(JSON.stringify(document.components.schemas).replaceAll('#/components/schemas/', '#/definitions/'))
  const compiled = await compile({
    type: 'object',
    properties: Object.fromEntries(Object.keys(schemas).map(name => [name, { $ref: `#/definitions/${name}` }])),
    required: Object.keys(schemas),
    additionalProperties: false,
    definitions: schemas,
  }, 'ApiSchemas')
  const lines = ['export interface ApiPaths {']
  /** @param {ContractSchema} schema @returns {string} */
  function schemaType(schema) {
    if (schema.$ref) {
      const name = schema.$ref.replace('#/components/schemas/', '')
      if (!Object.hasOwn(schemas, name)) throw new Error(`Unknown schema ${name}`)
      return `ApiSchemas[${JSON.stringify(name)}]`
    }
    const variants = schema.oneOf ?? schema.anyOf
    if (variants?.length) return variants.map(schemaType).join(' | ')
    throw new Error('Unsupported inline schema; extend generation explicitly')
  }
  for (const [path, methods] of Object.entries(document.paths)) {
    lines.push(`  ${JSON.stringify(path)}: {`)
    for (const [method, operation] of Object.entries(methods)) {
      if (!['get', 'post', 'put', 'patch', 'delete'].includes(method) || (operation.parameters?.length ?? 0) > 1) {
        throw new Error(`Unsupported contract shape at ${method.toUpperCase()} ${path}; extend generation explicitly`)
      }
      const parameters = operation.parameters ?? []
      if (parameters.some(parameter => !['path', 'query'].includes(parameter.in))) {
        throw new Error(`Unsupported parameter at ${method.toUpperCase()} ${path}; extend generation explicitly`)
      }
      lines.push(`    ${method}: {`)
      const queryParameter = parameters.find(parameter => parameter.in === 'query')
      if (queryParameter) {
        const union = queryParameter.schema?.type === 'boolean' ? 'boolean' : 'string'
        lines.push(`      parameters: { query: Record<string, ${union}> }`)
      }
      if (operation.requestBody) {
        const body = operation.requestBody.content['application/json']?.schema
        if (!body) throw new Error(`Unsupported request body at ${method} ${path}`)
        lines.push(`      requestBody: ${schemaType(body)}`)
      }
      lines.push('      responses: {')
      for (const [status, response] of Object.entries(operation.responses)) {
        const content = response.content
        const schema = content?.['application/json']?.schema ?? content?.['text/event-stream']?.schema ?? null
        if (status === '204' && !content) {
          lines.push(`      ${status}: void`)
          continue
        }
        if (!schema || !/^\d{3}$/.test(status) || Object.keys(content ?? {}).some(type => !['application/json', 'text/event-stream'].includes(type))) {
          throw new Error(`Unsupported response schema at ${method.toUpperCase()} ${path} ${status}`)
        }
        lines.push(`      ${status}: ${schemaType(schema)}`)
      }
      lines.push('    } }')
    }
    lines.push('  }')
  }
  lines.push('}', '')
  const outputs = [
    { path: join(root, 'docs/api/openapi.json'), content: contract },
    { path: join(root, 'frontend/app/types/generated/api.ts'), content: `/* Generated from backend OpenAPI. Run pnpm api:generate. Do not edit. */\n${compiled}\n${lines.join('\n')}` },
  ]
  for (const output of outputs) {
    if (check) {
      const existing = await readFile(output.path, 'utf8')
      if (existing !== output.content) throw new Error(`API contract drift: ${output.path}. Run pnpm api:generate.`)
    } else {
      await mkdir(dirname(output.path), { recursive: true })
      await writeFile(output.path, output.content, 'utf8')
    }
  }
  console.log(check ? 'API contracts are current.' : 'API contracts generated.')
} finally {
  await rm(temporary, { recursive: true, force: true })
}
