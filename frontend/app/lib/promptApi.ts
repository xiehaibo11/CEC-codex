import { apiRequest } from './apiClient'

export interface PromptTemplate {
  id: number
  key: string
  name: string
  description?: string | null
  templateText: string
  systemTemplateText: string
  isSystem: string
  isDeleted: string
  createdBy: string
  updatedBy?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface PromptBinding {
  id: number
  accountId: number
  accountName: string
  accountModel?: string | null
  promptTemplateId: number
  promptKey: string
  promptName: string
  updatedBy?: string | null
  updatedAt?: string | null
}

export interface PromptListResponse {
  templates: PromptTemplate[]
  bindings: PromptBinding[]
}

export interface PromptTemplateUpdateRequest {
  templateText: string
  description?: string
  updatedBy?: string
}

export interface PromptTemplateCreateRequest {
  name: string
  description?: string
  templateText?: string
  createdBy?: string
}

export interface PromptTemplateCopyRequest {
  newName?: string
  createdBy?: string
}

export interface PromptTemplateNameUpdateRequest {
  name: string
  description?: string
  updatedBy?: string
}

export interface PromptBindingUpsertRequest {
  id?: number
  accountId: number
  promptTemplateId: number
  updatedBy?: string
}

export async function getPromptTemplates(): Promise<PromptListResponse> {
  const response = await apiRequest('/prompts')
  return response.json()
}

export async function updatePromptTemplate(
  key: string,
  payload: PromptTemplateUpdateRequest,
): Promise<PromptTemplate> {
  const response = await apiRequest(`/prompts/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function createPromptTemplate(
  payload: PromptTemplateCreateRequest,
): Promise<PromptTemplate> {
  const response = await apiRequest('/prompts', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function copyPromptTemplate(
  templateId: number,
  payload: PromptTemplateCopyRequest,
): Promise<PromptTemplate> {
  const response = await apiRequest(`/prompts/${templateId}/copy`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function deletePromptTemplate(templateId: number): Promise<void> {
  await apiRequest(`/prompts/${templateId}`, {
    method: 'DELETE',
  })
}

export async function updatePromptTemplateName(
  templateId: number,
  payload: PromptTemplateNameUpdateRequest,
): Promise<PromptTemplate> {
  const response = await apiRequest(`/prompts/${templateId}/name`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function upsertPromptBinding(
  payload: PromptBindingUpsertRequest,
): Promise<PromptBinding> {
  const response = await apiRequest('/prompts/bindings', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return response.json()
}

export async function deletePromptBinding(bindingId: number): Promise<void> {
  await apiRequest(`/prompts/bindings/${bindingId}`, {
    method: 'DELETE',
  })
}

export interface VariablesReferenceResponse {
  content: string
}

export async function getVariablesReference(lang: string = 'en'): Promise<VariablesReferenceResponse> {
  const response = await apiRequest(`/prompts/variables-reference?lang=${lang}`)
  return response.json()
}

export interface PromptPreviewRequest {
  templateText?: string
  promptTemplateKey?: string
  accountIds: number[]
  symbols?: string[]
  exchanges?: string[]
}

export interface PromptPreviewItem {
  accountId: number
  accountName: string
  symbols: string[]
  filledPrompt: string
  exchange?: string
}

export interface PromptPreviewResponse {
  previews: PromptPreviewItem[]
}

export async function previewPrompt(
  payload: PromptPreviewRequest,
): Promise<PromptPreviewResponse> {
  const response = await apiRequest('/prompts/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return response.json()
}
