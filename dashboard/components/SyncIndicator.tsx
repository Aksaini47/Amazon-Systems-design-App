'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

type SyncJob = {
  job_name: string;
  last_run: string;
  status: string;
  message: string;
};

export function SyncIndicator() {
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const data = await api.getSyncStatus();
        setJobs(data);
        setIsSyncing(data.some(j => j.status === 'running' || j.status === 'pending'));
      } catch (err) {
        console.error('Failed to poll sync status', err);
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (jobs.length === 0) return null;

  return (
    <div className="flex items-center gap-4 px-3 py-1 bg-gray-800/50 rounded-full border border-gray-700/50">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isSyncing ? 'bg-blue-500 animate-pulse' : 'bg-green-500'}`} />
        <span className="text-[10px] uppercase tracking-wider font-bold text-gray-400">
          {isSyncing ? 'Syncing Amazon...' : 'Systems Ready'}
        </span>
      </div>
      
      {jobs.map(job => (
        <div key={job.job_name} className="hidden md:block">
          <div className="text-[9px] text-gray-500 uppercase leading-none">{job.job_name}</div>
          <div className="text-[10px] text-gray-300 font-medium">
            {job.status === 'running' ? 'In Progress' : 
             job.last_run ? new Date(job.last_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Never'}
          </div>
        </div>
      ))}
    </div>
  );
}
