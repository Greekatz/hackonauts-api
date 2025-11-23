import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fetchWithFallback, postWithFallback } from '@/lib/api';
import { CardSkeleton } from '@/components/SkeletonLoader';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from '@/hooks/use-toast';
import {
  Activity,
  AlertTriangle,
  Server,
  Database,
  RefreshCw,
  Zap,
  Clock,
  CheckCircle,
  XCircle,
} from 'lucide-react';

interface SystemStatus {
  status: string;
  version: string;
  uptime_seconds?: number;
  database_connected?: boolean;
  watsonx_configured?: boolean;
  slack_configured?: boolean;
  monitoring_active?: boolean;
}

interface BufferStats {
  logs_count: number;
  metrics_count: number;
  oldest_log?: string;
  newest_log?: string;
}

export default function Debug() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [bufferStats, setBufferStats] = useState<BufferStats | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [statusData, healthData] = await Promise.all([
        fetchWithFallback<SystemStatus>('/status', { status: 'unknown', version: 'unknown' }),
        fetchWithFallback<any>('/health', { status: 'unknown' }),
      ]);

      setSystemStatus(statusData);
      setHealth(healthData);

      // Try to get buffer stats
      const bufferData = await fetchWithFallback<BufferStats>('/debug/buffer', {
        logs_count: 0,
        metrics_count: 0,
      });
      setBufferStats(bufferData);
    } catch (e) {
      console.error('Failed to load debug data', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
    toast({ title: 'Refreshed', description: 'Debug data updated' });
  };

  const handleTriggerMonitoring = async () => {
    toast({ title: 'Triggering', description: 'Running monitoring check...' });
    const result = await postWithFallback('/agent/trigger', {}, { status: 'triggered' });
    toast({
      title: 'Monitoring Complete',
      description: result.anomaly_detected ? 'Anomaly detected!' : 'No issues found',
    });
  };

  const handleForceRCA = async () => {
    toast({ title: 'Analyzing', description: 'Running RCA on recent data...' });
    await postWithFallback('/agent/rerun', {}, { status: 'completed' });
    toast({ title: 'RCA Complete', description: 'Analysis finished' });
  };

  if (loading) return <CardSkeleton />;

  const formatUptime = (seconds?: number) => {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Debug</h1>
          <p className="text-muted-foreground">System diagnostics and controls</p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* System Status Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <Server className="h-5 w-5 text-primary" />
            <h3 className="font-semibold">API Server</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Status</span>
              <Badge className={health?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}>
                {health?.status || 'Unknown'}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Version</span>
              <span className="font-mono text-xs">{systemStatus?.version || 'Unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Uptime</span>
              <span>{formatUptime(systemStatus?.uptime_seconds)}</span>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <Database className="h-5 w-5 text-primary" />
            <h3 className="font-semibold">Connections</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Database</span>
              {systemStatus?.database_connected ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">watsonx</span>
              {systemStatus?.watsonx_configured ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Slack</span>
              {systemStatus?.slack_configured ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <Activity className="h-5 w-5 text-primary" />
            <h3 className="font-semibold">Monitoring</h3>
          </div>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Status</span>
              <Badge className={systemStatus?.monitoring_active ? 'bg-green-500' : 'bg-yellow-500'}>
                {systemStatus?.monitoring_active ? 'Active' : 'Idle'}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Interval</span>
              <span>5 minutes</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Logs Buffered</span>
              <span>{bufferStats?.logs_count || 0}</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Actions */}
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <AlertTriangle className="h-5 w-5 text-primary" />
          <h3 className="font-semibold">Actions</h3>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Button onClick={handleTriggerMonitoring} className="w-full gap-2">
              <Zap className="h-4 w-4" />
              Trigger Monitoring Check
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              Manually run the LLM monitoring on current buffered data
            </p>
          </div>
          <div>
            <Button onClick={handleForceRCA} variant="outline" className="w-full gap-2">
              <Clock className="h-4 w-4" />
              Force RCA Analysis
            </Button>
            <p className="text-xs text-muted-foreground mt-2">
              Re-run root cause analysis on recent incidents
            </p>
          </div>
        </div>
      </Card>

      {/* Buffer Stats */}
      {bufferStats && (
        <Card className="p-6">
          <h3 className="font-semibold mb-4">Ingestion Buffer</h3>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Logs in Buffer</span>
                <span className="font-mono">{bufferStats.logs_count}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Metrics in Buffer</span>
                <span className="font-mono">{bufferStats.metrics_count}</span>
              </div>
            </div>
            <div className="space-y-2">
              {bufferStats.oldest_log && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Oldest Log</span>
                  <span className="font-mono text-xs">
                    {new Date(bufferStats.oldest_log).toLocaleString()}
                  </span>
                </div>
              )}
              {bufferStats.newest_log && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Newest Log</span>
                  <span className="font-mono text-xs">
                    {new Date(bufferStats.newest_log).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Raw Health Response */}
      <Card className="p-6">
        <h3 className="font-semibold mb-4">Raw Health Response</h3>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-xs font-mono">
          {JSON.stringify(health, null, 2)}
        </pre>
      </Card>
    </motion.div>
  );
}
