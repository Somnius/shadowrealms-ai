import { useEffect } from 'react';
import { useToast } from '../design';
import { setTransientHandler } from './http';

/**
 * Rate limits (429) and short outages (503) on signed-in requests: one friendly toast with the wait
 * time (the same id, so a burst of failing requests shows a single toast). Never a logout.
 */
export default function SessionNotices() {
  const { toast } = useToast();
  useEffect(() => {
    setTransientHandler(({ message }) => {
      if (message) toast({ id: 'sr-transient', tone: 'warn', title: message, duration: 7000 });
    });
    return () => setTransientHandler(null);
  }, [toast]);
  return null;
}
