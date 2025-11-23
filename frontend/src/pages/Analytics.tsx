import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fetchWithFallback } from '@/lib/api';
import { ChartSkeleton } from '@/components/SkeletonLoader';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  TrendingDown,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  Clock,
  Activity,
  Database,
  Zap,
  FileText,
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export default function Analytics() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAnalytics = async () => {
      const data = await fetchWithFallback('/analytics', null);
      setAnalytics(data);
      setLoading(false);
    };
    loadAnalytics();
  }, []);

  if (loading) return <ChartSkeleton />;

  // Check if we have any real data
  const hasData = analytics && (
    analytics.incidentStats?.total > 0 ||
    analytics.logStats?.total_logs > 0 ||
    analytics.incidentTrends?.some((d: any) => d.sev1 + d.sev2 + d.sev3 > 0)
  );

  if (!hasData) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-6"
      >
        <div>
          <h1 className="text-3xl font-bold">Analytics</h1>
          <p className="text-muted-foreground">Performance metrics and incident trends</p>
        </div>

        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="p-4 rounded-full bg-blue-500/10">
              <Activity className="h-12 w-12 text-blue-500" />
            </div>
            <h2 className="text-2xl font-semibold">No Data Yet</h2>
            <p className="text-muted-foreground max-w-md">
              Analytics will appear here once the system starts receiving logs and metrics.
              Run the test server or connect your services to start seeing data.
            </p>
          </div>
        </Card>
      </motion.div>
    );
  }

  const MetricCard = ({ title, current, previous, unit, trend, icon: Icon }: any) => (
    <Card className="p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm text-muted-foreground mb-2">{title}</h3>
          <div className="flex items-end gap-2">
            <span className="text-3xl font-bold">{current || 0}</span>
            <span className="text-muted-foreground mb-1">{unit}</span>
          </div>
          {previous > 0 && (
            <div className="flex items-center gap-1 mt-2 text-sm">
              {trend === 'down' ? (
                <>
                  <TrendingDown className="h-4 w-4 text-green-500" />
                  <span className="text-green-500">
                    -{Math.abs(((1 - current / previous) * 100)).toFixed(1)}%
                  </span>
                </>
              ) : (
                <>
                  <TrendingUp className="h-4 w-4 text-red-500" />
                  <span className="text-red-500">
                    +{Math.abs(((current / previous - 1) * 100)).toFixed(1)}%
                  </span>
                </>
              )}
              <span className="text-muted-foreground ml-1">vs previous</span>
            </div>
          )}
        </div>
        {Icon && (
          <div className="p-3 rounded-lg bg-muted">
            <Icon className="h-5 w-5 text-muted-foreground" />
          </div>
        )}
      </div>
    </Card>
  );

  const StatCard = ({ title, value, icon: Icon, color }: any) => (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-muted-foreground">{title}</p>
        </div>
      </div>
    </Card>
  );

  // Prepare incident status data for pie chart
  const incidentStatusData = analytics?.incidentStats ? [
    { name: 'Open', value: analytics.incidentStats.open, color: '#ef4444' },
    { name: 'Investigating', value: analytics.incidentStats.investigating, color: '#f97316' },
    { name: 'Resolved', value: analytics.incidentStats.resolved, color: '#22c55e' },
  ].filter(d => d.value > 0) : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-3xl font-bold">Analytics</h1>
        <p className="text-muted-foreground">Performance metrics and incident trends</p>
      </div>

      {/* Key Metrics */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Mean Time to Acknowledge"
          current={analytics?.mtta?.current}
          previous={analytics?.mtta?.previous}
          unit="min"
          trend={analytics?.mtta?.trend}
          icon={Clock}
        />
        <MetricCard
          title="Mean Time to Resolve"
          current={analytics?.mttr?.current}
          previous={analytics?.mttr?.previous}
          unit="min"
          trend={analytics?.mttr?.trend}
          icon={CheckCircle}
        />
        <StatCard
          title="Total Incidents"
          value={analytics?.incidentStats?.total || 0}
          icon={AlertCircle}
          color="bg-red-500"
        />
        <StatCard
          title="Logs Ingested"
          value={analytics?.logStats?.total_logs || 0}
          icon={FileText}
          color="bg-blue-500"
        />
      </div>

      {/* System Stats */}
      <div className="grid md:grid-cols-4 gap-4">
        <StatCard
          title="Open Incidents"
          value={analytics?.incidentStats?.open || 0}
          icon={AlertCircle}
          color="bg-red-500"
        />
        <StatCard
          title="Investigating"
          value={analytics?.incidentStats?.investigating || 0}
          icon={Activity}
          color="bg-orange-500"
        />
        <StatCard
          title="Resolved"
          value={analytics?.incidentStats?.resolved || 0}
          icon={CheckCircle}
          color="bg-green-500"
        />
        <StatCard
          title="Error Logs"
          value={analytics?.logStats?.error_logs || 0}
          icon={Zap}
          color="bg-yellow-500"
        />
      </div>

      {/* Incident Trends Chart */}
      {analytics?.incidentTrends?.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Incident Trends (7 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analytics.incidentTrends}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tickFormatter={(val) => new Date(val).toLocaleDateString('en-US', { weekday: 'short' })}
                className="text-muted-foreground"
              />
              <YAxis className="text-muted-foreground" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
              />
              <Legend />
              <Bar dataKey="sev1" fill="#ef4444" name="Critical (SEV1)" />
              <Bar dataKey="sev2" fill="#f97316" name="High (SEV2)" />
              <Bar dataKey="sev3" fill="#eab308" name="Medium (SEV3)" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Error Rates by Service */}
        {analytics?.errorRates?.length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Error Rate by Service (%)</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={analytics.errorRates} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis type="number" className="text-muted-foreground" />
                <YAxis dataKey="service" type="category" width={120} className="text-muted-foreground" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="rate" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* Incident Status Distribution */}
        {incidentStatusData.length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Incident Status Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={incidentStatusData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {incidentStatusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* P95 Latency */}
        {analytics?.latencyP95?.length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">P95 Latency (ms)</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={analytics.latencyP95}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="hour" className="text-muted-foreground" />
                <YAxis className="text-muted-foreground" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: '#3b82f6' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* Data Ingestion Stats */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Data Ingestion</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-blue-500" />
                <span>Log Entries</span>
              </div>
              <Badge variant="secondary" className="text-lg">
                {analytics?.logStats?.total_logs || 0}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-3">
                <Activity className="h-5 w-5 text-purple-500" />
                <span>Metric Entries</span>
              </div>
              <Badge variant="secondary" className="text-lg">
                {analytics?.logStats?.total_metrics || 0}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-3">
                <Database className="h-5 w-5 text-green-500" />
                <span>Snapshots</span>
              </div>
              <Badge variant="secondary" className="text-lg">
                {analytics?.logStats?.total_snapshots || 0}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-3">
                <Zap className="h-5 w-5 text-red-500" />
                <span>Error Logs</span>
              </div>
              <Badge variant="secondary" className="text-lg">
                {analytics?.logStats?.error_logs || 0}
              </Badge>
            </div>
          </div>
        </Card>
      </div>

      {/* Autoheal History */}
      {analytics?.autohealHistory?.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Autoheal Actions</h3>
          <div className="space-y-3">
            {analytics.autohealHistory.slice(-5).reverse().map((action: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-muted rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded ${action.success ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                    {action.success ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-500" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium">{action.action}</p>
                    <p className="text-sm text-muted-foreground">
                      {action.service || 'N/A'} - {action.message?.slice(0, 50)}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant={action.dry_run ? 'outline' : 'default'}>
                    {action.dry_run ? 'Dry Run' : 'Executed'}
                  </Badge>
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(action.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </motion.div>
  );
}
