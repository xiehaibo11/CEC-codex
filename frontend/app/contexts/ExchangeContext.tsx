/**
 * Exchange selection context for managing current exchange state
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  ExchangeId,
  ExchangeInfo,
  ExchangeContextType,
  DEFAULT_EXCHANGE,
  EXCHANGE_DISPLAY_NAMES,
  EXCHANGE_STATUS_COLORS
} from '@/lib/types/exchange';
import { isAuthenticated } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

const ExchangeContext = createContext<ExchangeContextType | undefined>(undefined);

interface ExchangeProviderProps {
  children: ReactNode;
}

// Storage key for persisting exchange selection
const STORAGE_KEY = 'hyper-alpha-arena-selected-exchange';
const VALID_EXCHANGE_IDS: ExchangeId[] = ['hyperliquid', 'binance', 'hibt', 'aster'];

export function ExchangeProvider({ children }: ExchangeProviderProps) {
  const [currentExchange, setCurrentExchange] = useState<ExchangeId>(DEFAULT_EXCHANGE);
  const [isLoading, setIsLoading] = useState(false);
  const { loading: authLoading } = useAuth();

  // Initialize exchange selection from backend
  useEffect(() => {
    const loadExchangeConfig = async () => {
      if (authLoading) return;  // 等待 auth 初始化完成
      // Skip the protected backend call when not logged in; use localStorage default silently.
      if (!isAuthenticated()) {
        try {
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored && VALID_EXCHANGE_IDS.includes(stored as ExchangeId)) {
            setCurrentExchange(stored as ExchangeId);
          }
        } catch {
          // Ignore localStorage access errors and keep the default exchange.
        }
        return;
      }
      try {
        const response = await fetch('/api/users/exchange-config');
        if (response.ok) {
          const data = await response.json();
          if (data.selected_exchange && VALID_EXCHANGE_IDS.includes(data.selected_exchange as ExchangeId)) {
            setCurrentExchange(data.selected_exchange as ExchangeId);
          }
        } else {
          // Fallback to localStorage if backend fails
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored && VALID_EXCHANGE_IDS.includes(stored as ExchangeId)) {
            setCurrentExchange(stored as ExchangeId);
          }
        }
      } catch (error) {
        console.warn('Failed to load exchange config from backend, using localStorage:', error);
        // Fallback to localStorage
        try {
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored && VALID_EXCHANGE_IDS.includes(stored as ExchangeId)) {
            setCurrentExchange(stored as ExchangeId);
          }
        } catch (localError) {
          console.warn('Failed to load from localStorage:', localError);
        }
      }
    };

    loadExchangeConfig();
  }, [authLoading]);

  // Exchange data with selection state
  const exchanges: ExchangeInfo[] = [
    {
      id: 'hyperliquid',
      name: 'Hyperliquid',
      displayName: 'Hyperliquid',
      selectable: true,
      selected: currentExchange === 'hyperliquid',
      apiSupported: true,
      comingSoon: false,
      logo: '/static/hyperliquid_logo.svg',
      description: '#1 Decentralized Perpetual DEX',
      features: ['No KYC Required', 'On-chain Settlement', 'Testnet Available'],
      buttonText: 'Open Futures',
      buttonVariant: 'default'
    },
    {
      id: 'binance',
      name: 'Binance',
      displayName: 'Binance',
      selectable: false,
      selected: currentExchange === 'binance',
      apiSupported: false,
      comingSoon: true,
      logo: '/static/binance_logo.svg',
      description: '#1 Global CEX by Volume',
      features: ['KYC Required', 'High Liquidity', 'Testnet Available'],
      referralLink: 'https://www.binance.com/en/join?ref=HYPERSVIP',
      buttonText: 'Register First',
      buttonVariant: 'outline'
    },
    {
      id: 'hibt',
      name: 'HiBT',
      displayName: 'HiBT',
      selectable: false,
      selected: currentExchange === 'hibt',
      apiSupported: true,
      comingSoon: false,
      logo: '',
      description: 'Centralized perpetual futures API',
      features: ['Perpetual Futures', 'Access Key API', 'Market Data'],
      buttonText: 'Configure Wallet',
      buttonVariant: 'outline'
    },
    {
      id: 'aster',
      name: 'Aster DEX',
      displayName: 'Aster DEX',
      selectable: false,
      selected: currentExchange === 'aster',
      apiSupported: false,
      comingSoon: true,
      logo: '/static/aster_logo.png',
      description: 'Binance-compatible decentralized exchange',
      features: ['Lower Fees', 'Multi-chain Support', 'API Wallet Security'],
      referralLink: 'https://www.asterdex.com/zh-CN/referral/2b5924',
      buttonText: 'Register First',
      buttonVariant: 'outline'
    }
  ];

  const selectExchange = async (exchangeId: ExchangeId) => {
    if (exchangeId === currentExchange) return;

    // Only allow selection of supported exchanges
    const exchange = exchanges.find(ex => ex.id === exchangeId);
    if (!exchange?.selectable) {
      console.warn(`Exchange ${exchangeId} is not selectable yet`);
      return;
    }

    setIsLoading(true);

    try {
      // Save to backend first
      const response = await fetch('/api/users/exchange-config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ selected_exchange: exchangeId }),
      });

      if (!response.ok) {
        throw new Error(`Backend save failed: ${response.status}`);
      }

      // Update state
      setCurrentExchange(exchangeId);

      // Also persist to localStorage as backup
      localStorage.setItem(STORAGE_KEY, exchangeId);

      console.log(`Exchange switched to: ${EXCHANGE_DISPLAY_NAMES[exchangeId]}`);
    } catch (error) {
      console.error('Failed to switch exchange:', error);
      // Try localStorage fallback
      try {
        localStorage.setItem(STORAGE_KEY, exchangeId);
        setCurrentExchange(exchangeId);
        console.log(`Exchange switched to: ${EXCHANGE_DISPLAY_NAMES[exchangeId]} (localStorage fallback)`);
      } catch (localError) {
        console.error('Failed to save to localStorage:', localError);
        // Revert on complete failure
        setCurrentExchange(currentExchange);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const contextValue: ExchangeContextType = {
    currentExchange,
    exchanges,
    selectExchange,
    isLoading
  };

  return (
    <ExchangeContext.Provider value={contextValue}>
      {children}
    </ExchangeContext.Provider>
  );
}

export function useExchange(): ExchangeContextType {
  const context = useContext(ExchangeContext);
  if (context === undefined) {
    throw new Error('useExchange must be used within an ExchangeProvider');
  }
  return context;
}

// Helper hooks for common use cases
export function useCurrentExchange(): ExchangeId {
  const { currentExchange } = useExchange();
  return currentExchange;
}

export function useCurrentExchangeInfo(): ExchangeInfo {
  const { currentExchange, exchanges } = useExchange();
  return exchanges.find(ex => ex.id === currentExchange) || exchanges[0];
}
