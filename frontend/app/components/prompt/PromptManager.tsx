import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'react-hot-toast'
import {
  getPromptTemplates,
  updatePromptTemplate,
  upsertPromptBinding,
  deletePromptBinding,
  getAccounts,
  createPromptTemplate,
  copyPromptTemplate,
  deletePromptTemplate,
  updatePromptTemplateName,
  getVariablesReference,
  type PromptTemplate,
  type PromptBinding,
  type TradingAccount,
} from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { Card } from '@/components/ui/card'
import PromptPreviewDialog from './PromptPreviewDialog'
import AiPromptChatModal from './AiPromptChatModal'
import BindingsPanel from './prompt-manager/BindingsPanel'
import PromptEditor from './prompt-manager/PromptEditor'
import PromptTemplateList from './prompt-manager/PromptTemplateList'
import TemplateDialogs from './prompt-manager/TemplateDialogs'
import VariablesReferenceDialog from './prompt-manager/VariablesReferenceDialog'
import { getAiAccountOptions, readInitialPromptViewId } from './prompt-manager/helpers'
import { DEFAULT_BINDING_FORM, type BindingFormState } from './prompt-manager/types'

export default function PromptManager() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [bindings, setBindings] = useState<PromptBinding[]>([])
  const [accounts, setAccounts] = useState<TradingAccount[]>([])
  const [accountsLoading, setAccountsLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [templateDraft, setTemplateDraft] = useState<string>('')
  const [nameDraft, setNameDraft] = useState<string>('')
  const [descriptionDraft, setDescriptionDraft] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [bindingSaving, setBindingSaving] = useState(false)
  const [bindingForm, setBindingForm] = useState<BindingFormState>(DEFAULT_BINDING_FORM)
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false)

  /**
   * Initial view ID from URL parameter: #prompt-management?view=ID
   * Parsed once at component mount to handle deep linking from Hyper AI.
   */
  const initialViewIdRef = useRef<number | null>(readInitialPromptViewId())

  const [newTemplateDialogOpen, setNewTemplateDialogOpen] = useState(false)
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateDescription, setNewTemplateDescription] = useState('')
  const [creating, setCreating] = useState(false)

  const [copyDialogOpen, setCopyDialogOpen] = useState(false)
  const [copyName, setCopyName] = useState('')
  const [copying, setCopying] = useState(false)

  const [aiChatModalOpen, setAiChatModalOpen] = useState(false)

  const [variablesRefModalOpen, setVariablesRefModalOpen] = useState(false)
  const [variablesRefContent, setVariablesRefContent] = useState<string>('')
  const [variablesRefLoading, setVariablesRefLoading] = useState(false)
  const [variablesRefLang, setVariablesRefLang] = useState<string>('')

  useEffect(() => {
    setVariablesRefContent('')
    setVariablesRefLang('')
  }, [i18n.language])

  const selectedTemplate = useMemo(
    () => templates.find((tpl) => tpl.id === selectedId) || null,
    [templates, selectedId],
  )

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const data = await getPromptTemplates()
      setTemplates(data.templates)
      setBindings(data.bindings)

      const initialViewId = initialViewIdRef.current
      const effectiveSelectedId = initialViewId ?? selectedId

      if (!effectiveSelectedId && data.templates.length > 0) {
        const first = data.templates[0]
        setSelectedId(first.id)
        setTemplateDraft(first.templateText)
        setNameDraft(first.name)
        setDescriptionDraft(first.description ?? '')
      } else if (effectiveSelectedId) {
        const tpl = data.templates.find((item) => item.id === effectiveSelectedId)
        if (tpl) {
          setSelectedId(effectiveSelectedId)
          setTemplateDraft(tpl.templateText)
          setNameDraft(tpl.name)
          setDescriptionDraft(tpl.description ?? '')
        }
      }

      initialViewIdRef.current = null
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to load prompt templates')
    } finally {
      setLoading(false)
    }
  }

  const loadAccounts = async () => {
    setAccountsLoading(true)
    try {
      const list = await getAccounts()
      setAccounts(list)
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to load AI traders')
    } finally {
      setAccountsLoading(false)
    }
  }

  useEffect(() => {
    loadTemplates()
    loadAccounts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSelectTemplate = (id: string) => {
    const numId = Number(id)
    setSelectedId(numId)
    const tpl = templates.find((item) => item.id === numId)
    setTemplateDraft(tpl?.templateText ?? '')
    setNameDraft(tpl?.name ?? '')
    setDescriptionDraft(tpl?.description ?? '')
  }

  const handleSaveTemplate = async () => {
    if (!selectedTemplate) return
    setSaving(true)
    try {
      const updated = await updatePromptTemplate(selectedTemplate.key, {
        templateText: templateDraft,
        description: descriptionDraft,
        updatedBy: 'ui',
      })

      if (nameDraft !== selectedTemplate.name) {
        await updatePromptTemplateName(selectedTemplate.id, {
          name: nameDraft,
          description: descriptionDraft,
          updatedBy: 'ui',
        })
      }

      setTemplates((prev) =>
        prev.map((tpl) =>
          tpl.id === selectedTemplate.id
            ? { ...tpl, ...updated, name: nameDraft, description: descriptionDraft }
            : tpl,
        ),
      )
      toast.success('Prompt template saved')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to save prompt template')
    } finally {
      setSaving(false)
    }
  }

  const handleCreateTemplate = async () => {
    if (!newTemplateName.trim()) {
      toast.error('Please enter a template name')
      return
    }

    setCreating(true)
    try {
      const created = await createPromptTemplate({
        name: newTemplateName,
        description: newTemplateDescription,
        createdBy: 'ui',
      })

      setTemplates((prev) => [created, ...prev])
      setSelectedId(created.id)
      setTemplateDraft(created.templateText)
      setNameDraft(created.name)
      setDescriptionDraft(created.description ?? '')

      setNewTemplateDialogOpen(false)
      setNewTemplateName('')
      setNewTemplateDescription('')
      toast.success('Template created')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to create template')
    } finally {
      setCreating(false)
    }
  }

  const handleCopyTemplate = async () => {
    if (!selectedTemplate) return

    setCopying(true)
    try {
      const copied = await copyPromptTemplate(selectedTemplate.id, {
        newName: copyName || undefined,
        createdBy: 'ui',
      })

      setTemplates((prev) => [copied, ...prev])
      setSelectedId(copied.id)
      setTemplateDraft(copied.templateText)
      setNameDraft(copied.name)
      setDescriptionDraft(copied.description ?? '')

      setCopyDialogOpen(false)
      setCopyName('')
      toast.success('Template copied')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to copy template')
    } finally {
      setCopying(false)
    }
  }

  const handleDeleteTemplate = async () => {
    if (!selectedTemplate) return

    if (selectedTemplate.isSystem === 'true') {
      toast.error('Cannot delete system templates')
      return
    }

    if (!confirm(`Delete template "${selectedTemplate.name}"?`)) {
      return
    }

    try {
      await deletePromptTemplate(selectedTemplate.id)
      setTemplates((prev) => prev.filter((tpl) => tpl.id !== selectedTemplate.id))

      const remaining = templates.filter((tpl) => tpl.id !== selectedTemplate.id)
      if (remaining.length > 0) {
        setSelectedId(remaining[0].id)
        setTemplateDraft(remaining[0].templateText)
        setNameDraft(remaining[0].name)
        setDescriptionDraft(remaining[0].description ?? '')
      } else {
        setSelectedId(null)
        setTemplateDraft('')
        setNameDraft('')
        setDescriptionDraft('')
      }

      toast.success('Template deleted')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to delete template')
    }
  }

  const handleBindingSubmit = async () => {
    if (!bindingForm.accountId) {
      toast.error('Please select an AI trader')
      return
    }
    if (!bindingForm.promptTemplateId) {
      toast.error('Please select a prompt template')
      return
    }

    setBindingSaving(true)
    try {
      const payload = await upsertPromptBinding({
        id: bindingForm.id,
        accountId: bindingForm.accountId,
        promptTemplateId: bindingForm.promptTemplateId,
        updatedBy: 'ui',
      })

      setBindings((prev) => {
        const existingIndex = prev.findIndex((item) => item.id === payload.id)
        if (existingIndex !== -1) {
          const next = [...prev]
          next[existingIndex] = payload
          return next
        }
        return [...prev, payload].sort((a, b) => a.accountName.localeCompare(b.accountName))
      })
      setBindingForm(DEFAULT_BINDING_FORM)
      toast.success('Prompt binding saved')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to save binding')
    } finally {
      setBindingSaving(false)
    }
  }

  const handleDeleteBinding = async (bindingId: number) => {
    try {
      await deletePromptBinding(bindingId)
      setBindings((prev) => prev.filter((item) => item.id !== bindingId))
      toast.success('Binding deleted')
    } catch (err) {
      console.error(err)
      toast.error(err instanceof Error ? err.message : 'Failed to delete binding')
    }
  }

  const handleEditBinding = (binding: PromptBinding) => {
    setBindingForm({
      id: binding.id,
      accountId: binding.accountId,
      promptTemplateId: binding.promptTemplateId,
    })
  }

  const handleAiWriteClick = () => {
    if (!user) {
      toast.error('Please log in to use this feature')
      return
    }

    setAiChatModalOpen(true)
  }

  const handleOpenVariablesRef = async () => {
    setVariablesRefModalOpen(true)
    const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en'
    if (!variablesRefContent || variablesRefLang !== currentLang) {
      setVariablesRefLoading(true)
      try {
        const data = await getVariablesReference(currentLang)
        setVariablesRefContent(data.content)
        setVariablesRefLang(currentLang)
      } catch (err) {
        console.error(err)
        toast.error(t('prompt.loadVariablesFailed', 'Failed to load variables reference'))
      } finally {
        setVariablesRefLoading(false)
      }
    }
  }

  useEffect(() => {
    if (selectedTemplate) {
      setTemplateDraft(selectedTemplate.templateText)
      setNameDraft(selectedTemplate.name)
      setDescriptionDraft(selectedTemplate.description ?? '')
    }
  }, [selectedTemplate])

  const accountOptions = useMemo(() => getAiAccountOptions(accounts), [accounts])

  return (
    <>
      <div className="h-full w-full overflow-hidden flex flex-col gap-4">
        <div className="flex flex-col lg:flex-row gap-4 h-full overflow-hidden">
          <div className="flex-1 flex flex-col h-full gap-4 overflow-hidden">
            <Card className="flex-1 flex flex-col h-full overflow-hidden">
              <PromptTemplateList
                templates={templates}
                selectedId={selectedId}
                selectedTemplate={selectedTemplate}
                loading={loading}
                onOpenVariablesRef={handleOpenVariablesRef}
                onSelectTemplate={handleSelectTemplate}
                onCreateClick={() => setNewTemplateDialogOpen(true)}
                onCopyClick={() => setCopyDialogOpen(true)}
                onDeleteTemplate={handleDeleteTemplate}
              >
                <PromptEditor
                  selectedTemplate={selectedTemplate}
                  nameDraft={nameDraft}
                  descriptionDraft={descriptionDraft}
                  templateDraft={templateDraft}
                  saving={saving}
                  onNameChange={setNameDraft}
                  onDescriptionChange={setDescriptionDraft}
                  onTemplateChange={setTemplateDraft}
                  onAiWriteClick={handleAiWriteClick}
                  onPreviewClick={() => setPreviewDialogOpen(true)}
                  onSaveTemplate={handleSaveTemplate}
                />
              </PromptTemplateList>
            </Card>
          </div>

          <BindingsPanel
            bindings={bindings}
            templates={templates}
            accountOptions={accountOptions}
            bindingForm={bindingForm}
            accountsLoading={accountsLoading}
            bindingSaving={bindingSaving}
            setBindingForm={setBindingForm}
            onEditBinding={handleEditBinding}
            onDeleteBinding={handleDeleteBinding}
            onSubmit={handleBindingSubmit}
          />
        </div>
      </div>

      {selectedTemplate && (
        <PromptPreviewDialog
          open={previewDialogOpen}
          onOpenChange={setPreviewDialogOpen}
          templateKey={selectedTemplate.key}
          templateName={selectedTemplate.name}
          templateText={templateDraft}
        />
      )}

      <TemplateDialogs
        selectedTemplate={selectedTemplate}
        newTemplateDialogOpen={newTemplateDialogOpen}
        newTemplateName={newTemplateName}
        newTemplateDescription={newTemplateDescription}
        creating={creating}
        copyDialogOpen={copyDialogOpen}
        copyName={copyName}
        copying={copying}
        onNewTemplateOpenChange={setNewTemplateDialogOpen}
        onNewTemplateNameChange={setNewTemplateName}
        onNewTemplateDescriptionChange={setNewTemplateDescription}
        onCreateTemplate={handleCreateTemplate}
        onCopyDialogOpenChange={setCopyDialogOpen}
        onCopyNameChange={setCopyName}
        onCopyTemplate={handleCopyTemplate}
      />

      <AiPromptChatModal
        open={aiChatModalOpen}
        onOpenChange={setAiChatModalOpen}
        accounts={accounts}
        accountsLoading={accountsLoading}
        onApplyPrompt={setTemplateDraft}
        promptId={selectedId}
        promptName={selectedTemplate?.name}
      />

      <VariablesReferenceDialog
        open={variablesRefModalOpen}
        onOpenChange={setVariablesRefModalOpen}
        loading={variablesRefLoading}
        content={variablesRefContent}
        onTryAiWrite={() => {
          setVariablesRefModalOpen(false)
          handleAiWriteClick()
        }}
      />
    </>
  )
}
