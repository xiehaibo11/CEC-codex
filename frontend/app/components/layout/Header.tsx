import { LogOut, UserCog } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { useAuth } from '@/contexts/AuthContext'
import { loadAuthConfig } from '@/lib/auth'

interface Account {
  id: number
  user_id: number
  name: string
  account_type: string
  initial_capital: number
  current_cash: number
  frozen_cash: number
}

interface HeaderProps {
  title?: string
  currentAccount?: Account | null
  showAccountSelector?: boolean
}

export default function Header({ title = 'Hyper Alpha Arena', currentAccount, showAccountSelector = false }: HeaderProps) {
  const { t } = useTranslation()
  const { user, loading, authEnabled, logout } = useAuth()

  const handleSignUp = () => {
    window.location.href = '/login'
  }

  const handleOpenAccount = async () => {
    const config = await loadAuthConfig()
    const authProvider = config?.authProvider || 'https://auth.bocail.com'
    window.open(`${authProvider}/account`, '_blank', 'noopener,noreferrer')
  }

  return (
    <header className="w-full border-b bg-background/50 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full py-2 px-3 md:px-4 flex items-center justify-between">
        <div className="flex items-center gap-2 md:gap-3">
          <h1 className="text-base md:text-xl font-bold truncate">{title}</h1>
        </div>

        {/* Right side controls - Hidden on mobile */}
        <div className="hidden md:flex items-center gap-3">
          {authEnabled && (
            <>
              {loading ? (
                <div className="w-20 h-9 bg-muted animate-pulse rounded-md" />
              ) : user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" className="relative h-9 w-9 rounded-full p-0">
                      <Avatar className="h-9 w-9">
                        <AvatarImage src={user.avatar} alt={user.displayName || user.name} />
                        <AvatarFallback className="text-xs">
                          {user.displayName?.[0] || user.name?.[0] || "U"}
                        </AvatarFallback>
                      </Avatar>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-56" align="end" forceMount>
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col space-y-1">
                        <p className="text-sm font-medium leading-none">
                          {user.displayName || user.name}
                        </p>
                        <p className="text-xs leading-none text-muted-foreground">
                          {user.email}
                        </p>
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={handleOpenAccount}>
                      <UserCog className="mr-2 h-4 w-4" />
                      <span>{t('header.myAccount', 'My Account')}</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={logout}>
                      <LogOut className="mr-2 h-4 w-4" />
                      <span>{t('header.signOut', 'Sign Out')}</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Button
                  onClick={handleSignUp}
                  size="sm"
                  className="px-4 py-2 text-sm font-medium"
                >
                  {t('header.login', 'Login')}
                </Button>
              )}
            </>
          )}
        </div>
      </div>

    </header>
  )
}
