import { useState, type FormEvent } from 'react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/contexts/AuthContext'

// Accepts a plain username (3-50 chars) or an email address.
const USERNAME_PATTERN =
  /^(?:[A-Za-z0-9_.-]{3,50}|[A-Za-z0-9_.+-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+)$/

type Mode = 'login' | 'register'

export default function LoginPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isRegister = mode === 'register'

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (submitting) return

    // Basic client-side validation matching backend rules.
    if (!USERNAME_PATTERN.test(username)) {
      toast.error('用户名需为 3-50 个字符(字母、数字、_ . -)或邮箱格式')
      return
    }
    if (password.length < 6) {
      toast.error('密码至少需要 6 个字符')
      return
    }
    if (isRegister && password !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }

    setSubmitting(true)
    try {
      if (isRegister) {
        await register(username, password)
      } else {
        await login(username, password)
      }
      window.location.href = '/'
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '认证失败')
      setSubmitting(false)
    }
  }

  const toggleMode = () => {
    setMode((prev) => (prev === 'login' ? 'register' : 'login'))
    setConfirmPassword('')
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
          返回
        </Button>

        <section className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-3">
            <img
              src="/arena_logo_app_small.png"
              alt="CEC-codex"
              className="h-10 w-10 rounded-md"
            />
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold leading-tight">CEC-codex</h1>
              <p className="text-sm text-muted-foreground">
                {isRegister ? '注册账号' : '登录'}
              </p>
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名或邮箱"
                disabled={submitting}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 个字符"
                disabled={submitting}
                required
              />
            </div>

            {isRegister && (
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">确认密码</Label>
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="请再次输入密码"
                  disabled={submitting}
                  required
                />
              </div>
            )}

            <Button type="submit" className="h-11 w-full" disabled={submitting}>
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span>{isRegister ? '注册' : '登录'}</span>
              )}
            </Button>
          </form>

          <div className="mt-4 text-center text-sm text-muted-foreground">
            {isRegister ? '已有账号?' : '还没有账号?'}{' '}
            <button
              type="button"
              className="font-medium text-foreground underline-offset-4 hover:underline"
              onClick={toggleMode}
              disabled={submitting}
            >
              {isRegister ? '去登录' : '去注册'}
            </button>
          </div>
        </section>
      </div>
    </main>
  )
}
