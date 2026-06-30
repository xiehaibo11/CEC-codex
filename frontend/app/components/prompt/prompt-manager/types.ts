export interface BindingFormState {
  id?: number
  accountId?: number
  promptTemplateId?: number
}

export const DEFAULT_BINDING_FORM: BindingFormState = {
  accountId: undefined,
  promptTemplateId: undefined,
}
