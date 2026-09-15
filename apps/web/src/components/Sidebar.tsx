'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { api } from '@/lib/api';
import {
  LayoutDashboard,
  Briefcase,
  UploadCloud,
  FileCheck,
  BarChart3,
  UserCheck,
  Settings,
  Sparkles,
  ExternalLink,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Offres & Veille', href: '/jobs', icon: Briefcase },
  { name: 'Importer des URLs', href: '/jobs/import', icon: UploadCloud },
  { name: 'Candidatures', href: '/applications', icon: FileCheck },
  { name: 'Analytique', href: '/analytics', icon: BarChart3 },
  { name: 'Profil Maître', href: '/candidate', icon: UserCheck },
  { name: 'Paramètres', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const health = useQuery({ queryKey: ['health'], queryFn: () => api.system.health(), refetchInterval: 60_000 });
  const online = health.isSuccess;

  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-slate-100 gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white shadow-sm shadow-indigo-200">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-slate-900 leading-none">Trema Jobs</h1>
          <span className="text-[11px] font-medium text-slate-400">Agent IA de Candidature</span>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-100 bg-slate-50/50 m-3 rounded-xl">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
          <span className="font-medium">Status API</span>
          <span
            className={`inline-flex items-center gap-1 font-semibold ${
              online ? 'text-emerald-600' : health.isError ? 'text-red-500' : 'text-slate-400'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                online ? 'bg-emerald-500 animate-pulse' : health.isError ? 'bg-red-500' : 'bg-slate-300'
              }`}
            ></span>
            {online ? 'Actif' : health.isError ? 'Hors ligne' : '…'}
          </span>
        </div>
        <p className="text-[11px] text-slate-400">
          FastAPI {health.data?.version ?? '2.0'} · Gemini {health.data?.services.gemini === 'configured' ? 'OK' : 'non configuré'}
        </p>
      </div>
    </aside>
  );
}
