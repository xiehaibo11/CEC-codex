import { useTranslation } from 'react-i18next'
import { ArrowRight, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface CompletionStepProps {
  onComplete: () => void
}

export function CompletionStep({ onComplete }: CompletionStepProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <CheckCircle2 className="w-8 h-8 text-green-500" />
      <p className="text-sm text-muted-foreground">
        {t('hyperAi.onboarding.profileSaved', 'Your profile has been saved!')}
      </p>
      <Button onClick={onComplete} size="lg" className="px-8">
        {t('hyperAi.onboarding.enterSystem', 'Enter System')}
        <ArrowRight className="w-4 h-4 ml-2" />
      </Button>
    </div>
  )
}
