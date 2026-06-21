import { useState } from 'react'
import { ArrowLeft, Chrome, Github, Loader2 } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import {
  getProviderSignInUrl,
  type OAuthProviderType,
} from '@/lib/auth'

const providerOptions: Array<{
  type: OAuthProviderType
  label: string
  icon: typeof Github
}> = [
  { type: 'GitHub', label: 'Continue with GitHub', icon: Github },
  { type: 'Google', label: 'Continue with Google', icon: Chrome },
]

export default function LoginPage() {
  const [loadingProvider, setLoadingProvider] = useState<OAuthProviderType | null>(null)

  const handleProviderLogin = async (providerType: OAuthProviderType) => {
    setLoadingProvider(providerType)
    try {
      const url = await getProviderSignInUrl(providerType)
      if (!url) {
        toast.error('Login provider is unavailable')
        setLoadingProvider(null)
        return
      }
      window.location.href = url
    } catch (error) {
      console.error('Failed to start provider login:', error)
      toast.error('Unable to start login')
      setLoadingProvider(null)
    }
  }

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-4 py-8">
        <Button
          type="button"
          variant="ghost"
          className="mb-6 w-fit px-2"
          onClick={() => {
            window.location.href = '/'
          }}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>

        <section className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <img
              src="/arena_logo_app_small.png"
              alt="Hyper Alpha Arena"
              className="h-10 w-10 rounded-md"
            />
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold leading-tight">Hyper Alpha Arena</h1>
              <p className="text-sm text-muted-foreground">Sign in</p>
            </div>
          </div>

          <div className="space-y-3">
            {providerOptions.map((provider) => {
              const Icon = provider.icon
              const isLoading = loadingProvider === provider.type
              return (
                <Button
                  key={provider.type}
                  type="button"
                  variant="outline"
                  className="h-11 w-full justify-start text-sm"
                  disabled={loadingProvider !== null}
                  onClick={() => handleProviderLogin(provider.type)}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                  <span className="truncate">{provider.label}</span>
                </Button>
              )
            })}
          </div>
        </section>
      </div>
    </main>
  )
}
