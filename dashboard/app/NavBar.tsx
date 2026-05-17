'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

import { SyncIndicator } from '@/components/SyncIndicator';

const NAV_LINKS = [
  { href: '/',        label: 'Orders'        },
  { href: '/returns', label: 'Returns'       },
  { href: '/fba',     label: 'FBA Shipments' },
];

export default function NavBar() {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 flex items-center gap-1 min-h-[56px]">
      <span className="font-bold text-white text-lg tracking-tight flex items-center pr-6 border-r border-gray-800 mr-3 self-stretch">
        RepairFully
      </span>

      <div className="flex items-stretch self-stretch">
        {NAV_LINKS.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`relative flex items-center px-4 text-sm transition-colors ${
              isActive(href)
                ? 'text-white font-medium'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {label}
            {isActive(href) && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500 rounded-t" />
            )}
          </Link>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-5">
        <SyncIndicator />
      </div>
    </nav>
  );
}

