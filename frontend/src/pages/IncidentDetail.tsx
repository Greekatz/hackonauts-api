import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { fetchWithFallback, postWithFallback } from '@/lib/api';
import { mockIncidentDetail } from '@/lib/mockData';
import { CardSkeleton } from '@/components/SkeletonLoader';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/hooks/use-toast';
import {
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  Play,
  Sparkles,
  Zap,
  RotateCw,
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function IncidentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [incident, setIncident] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadIncident = async () => {
      const data = await fetchWithFallback(`/incidents/${id}`, mockIncidentDetail);
      setIncident(data);
      setLoading(false);
    };
    loadIncident();
  }, [id]);

  const handleAcknowledge = async () => {
    await postWithFallback(`/incidents/${id}/acknowledge`, {}, { success: true });
    toast({ title: 'Incident Acknowledged', description: 'Team has been notified.' });
    navigate('/incidents');
  };

  const handleEscalate = async () => {
    await postWithFallback(`/incidents/${id}/escalate`, {}, { success: true });
    toast({ title: 'Incident Escalated', description: 'Senior engineers notified.' });
  };

  const handleRunPlan = async (planId: string) => {
    await postWithFallback(`/runbooks/${planId}/execute`, {}, { success: true });
    toast({ title: 'Runbook Executing', description: 'Automated recovery initiated...' });
  };

  const handleAutoHeal = async () => {
    await postWithFallback(`/incidents/${id}/auto-heal`, {}, { success: true });
    toast({ title: 'Auto-Heal Started', description: 'AI agent analyzing and applying fixes...' });
  };

  const handleTriggerAgent = async () => {
    await postWithFallback('/agent/trigger', { incident_id: id }, { success: true });
    toast({ title: 'Agent Triggered', description: 'Watsonx agent re-analyzing incident...' });
  };

  const handleRerunLoop = async () => {
    await postWithFallback('/agent/rerun', { incident_id: id }, { success: true });
    toast({ title: 'Loop Restarted', description: 'Agent loop restarted with fresh data...' });
  };

  if (loading) return <CardSkeleton />;
  if (!incident) return <div>Incident not found</div>;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/incidents')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{incident.title}</h1>
          <p className="text-muted-foreground">{incident.id} • {incident.service}</p>
        </div>
        <div className="flex gap-2">
          <Badge className="bg-severity-critical text-white">{incident.severity.toUpperCase()}</Badge>
          <Badge className="bg-status-open text-white">{incident.status}</Badge>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={handleAcknowledge} variant="outline" className="gap-2">
          <CheckCircle className="h-4 w-4" />
          Acknowledge
        </Button>
        <Button onClick={handleEscalate} variant="outline" className="gap-2">
          <AlertTriangle className="h-4 w-4" />
          Escalate
        </Button>
        <Button onClick={handleAutoHeal} className="gap-2 bg-primary">
          <Sparkles className="h-4 w-4" />
          Auto-Heal
        </Button>
        <Button onClick={handleTriggerAgent} variant="outline" className="gap-2">
          <Zap className="h-4 w-4" />
          Trigger Agent
        </Button>
        <Button onClick={handleRerunLoop} variant="outline" className="gap-2">
          <RotateCw className="h-4 w-4" />
          Re-run Loop
        </Button>
      </div>

      <Tabs defaultValue="summary" className="w-full">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="rca">RCA</TabsTrigger>
          <TabsTrigger value="plans">Recovery Plans</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-2">Summary</h3>
            <p className="text-muted-foreground">{incident.summary}</p>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Impact</p>
                <p className="font-medium">{incident.impact}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Affected Users</p>
                <p className="font-medium text-status-open">{incident.affectedUsers.toLocaleString()}</p>
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="rca" className="space-y-4">
          <Card className="p-6 prose prose-sm dark:prose-invert max-w-none">
            <div dangerouslySetInnerHTML={{ __html: incident.rca.replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
          </Card>
        </TabsContent>

        <TabsContent value="plans" className="space-y-4">
          {incident.plans.map((plan: any) => (
            <Card key={plan.id} className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold">{plan.name}</h3>
                  <Badge variant="outline" className="mt-2">{plan.status}</Badge>
                </div>
                <Button onClick={() => handleRunPlan(plan.id)} className="gap-2">
                  <Play className="h-4 w-4" />
                  Run Plan
                </Button>
              </div>
              <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                {plan.steps.map((step: string, i: number) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="logs" className="space-y-4">
          <Card className="p-6">
            <div className="font-mono text-sm space-y-2">
              {incident.logs.map((log: any, i: number) => (
                <div key={i} className="flex gap-4">
                  <span className="text-muted-foreground">{log.timestamp}</span>
                  <span className={
                    log.level === 'ERROR' ? 'text-status-open' :
                    log.level === 'WARN' ? 'text-status-acknowledged' :
                    'text-muted-foreground'
                  }>{log.level}</span>
                  <span>{log.message}</span>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-4">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Error Rate (%)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={incident.metrics.errorRate}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="hsl(var(--severity-critical))" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Latency (ms)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={incident.metrics.latency}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-2))" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </TabsContent>

        <TabsContent value="timeline" className="space-y-4">
          <Card className="p-6">
            <div className="space-y-4">
              {incident.timeline.map((event: any, i: number) => (
                <div key={i} className="flex gap-4 items-start">
                  <div className={`h-2 w-2 rounded-full mt-2 ${
                    event.type === 'critical' ? 'bg-status-open' :
                    event.type === 'error' ? 'bg-severity-high' :
                    event.type === 'warning' ? 'bg-status-acknowledged' :
                    'bg-primary'
                  }`} />
                  <div className="flex-1">
                    <p className="text-sm text-muted-foreground">{event.time}</p>
                    <p>{event.event}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}
