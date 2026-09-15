import type { Metadata } from 'next';
import { Toaster } from 'sonner';

import { Sidebar } from '@/components/Sidebar';

import { QueryProvider } from './providers/query-provider';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'Trema Job Search', template: '%s · Trema Job Search' },
  description: 'Agent IA de recherche d’emploi et de génération de candidatures sur mesure.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="min-h-screen antialiased">
        <QueryProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">{children}</div>
          </div>
          <Toaster richColors position="bottom-right" />
        </QueryProvider>
      </body>
    </html>
  );
}
