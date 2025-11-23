import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fetchWithFallback, postWithFallback } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { TableSkeleton } from '@/components/SkeletonLoader';
import {
  Play,
  RefreshCw,
  Server,
  Database,
  Trash2,
  ArrowLeftRight,
  RotateCcw,
  XCircle,
  HardDrive,
  Loader2,
  AlertTriangle,
  Clock,
  Zap,
} from 'lucide-react';

// Autoheal action definitions
const autohealActions = {
  restart_service: {
    name: 'Restart Service',
    icon: RefreshCw,
    description: 'Restart the affected service',
    parameters: [
      { name: 'platform', label: 'Platform', placeholder: 'docker / kubernetes / systemd', default: 'docker' },
    ],
  },
  scale_replicas: {
    name: 'Scale Replicas',
    icon: Server,
    description: 'Scale service replicas',
    parameters: [
      { name: 'replicas', label: 'Replica Count', placeholder: 'e.g., 5', type: 'number' },
      { name: 'platform', label: 'Platform', placeholder: 'kubernetes / docker_swarm', default: 'kubernetes' },
    ],
  },
  flush_cache: {
    name: 'Flush Cache',
    icon: Database,
    description: 'Clear cache to resolve stale data',
    parameters: [
      { name: 'cache_type', label: 'Cache Type', placeholder: 'redis / memcached', default: 'redis' },
    ],
  },
  clear_queue: {
    name: 'Clear Queue',
    icon: Trash2,
    description: 'Purge stuck messages from queue',
    parameters: [
      { name: 'queue_name', label: 'Queue Name', placeholder: 'e.g., orders-queue' },
      { name: 'queue_type', label: 'Queue Type', placeholder: 'rabbitmq / redis', default: 'rabbitmq' },
    ],
  },
  reroute_traffic: {
    name: 'Reroute Traffic',
    icon: ArrowLeftRight,
    description: 'Redirect traffic away from unhealthy instances',
    parameters: [
      { name: 'target', label: 'Target', placeholder: 'e.g., healthy', default: 'healthy' },
    ],
  },
  rollback_deployment: {
    name: 'Rollback Deployment',
    icon: RotateCcw,
    description: 'Rollback to previous version',
    parameters: [
      { name: 'revision', label: 'Revision (optional)', placeholder: 'e.g., 3', type: 'number' },
    ],
  },
  kill_process: {
    name: 'Kill Process',
    icon: XCircle,
    description: 'Terminate runaway process',
    parameters: [
      { name: 'pid', label: 'Process ID', placeholder: 'e.g., 12345', type: 'number' },
      { name: 'signal', label: 'Signal', placeholder: 'TERM / KILL', default: 'TERM' },
    ],
  },
  clear_disk: {
    name: 'Clear Disk Space',
    icon: HardDrive,
    description: 'Remove old files to free space',
    parameters: [
      { name: 'path', label: 'Path', placeholder: 'e.g., /var/log', default: '/tmp' },
      { name: 'pattern', label: 'Pattern', placeholder: 'e.g., *.log', default: '*.log' },
    ],
  },
};

// Map incident types to suggested autoheal actions
const incidentActionMap: Record<string, string[]> = {
  'memory': ['restart_service', 'scale_replicas', 'clear_disk'],
  'cpu': ['restart_service', 'scale_replicas', 'kill_process'],
  'connection': ['restart_service', 'flush_cache', 'scale_replicas'],
  'database': ['restart_service', 'flush_cache', 'clear_queue'],
  'cache': ['flush_cache', 'restart_service'],
  'queue': ['clear_queue', 'restart_service', 'scale_replicas'],
  'latency': ['scale_replicas', 'reroute_traffic', 'flush_cache'],
  'error': ['restart_service', 'rollback_deployment', 'reroute_traffic'],
  'disk': ['clear_disk', 'restart_service'],
  'deployment': ['rollback_deployment', 'restart_service'],
  'default': ['restart_service', 'scale_replicas', 'rollback_deployment'],
};

function getSuggestedActions(incident: any): string[] {
  const title = (incident.title || '').toLowerCase();
  const description = (incident.description || '').toLowerCase();
  const combined = `${title} ${description}`;

  for (const [keyword, actions] of Object.entries(incidentActionMap)) {
    if (keyword !== 'default' && combined.includes(keyword)) {
      return actions;
    }
  }
  return incidentActionMap.default;
}

function getSeverityColor(severity: string) {
  const colors: Record<string, string> = {
    sev1: 'bg-red-500 text-white',
    sev2: 'bg-orange-500 text-white',
    sev3: 'bg-yellow-500 text-black',
    critical: 'bg-red-500 text-white',
    high: 'bg-orange-500 text-white',
    medium: 'bg-yellow-500 text-black',
    low: 'bg-blue-500 text-white',
  };
  return colors[severity?.toLowerCase()] || 'bg-gray-500 text-white';
}

export default function Runbooks() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedIncident, setExpandedIncident] = useState<string | null>(null);
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [formData, setFormData] = useState<Record<string, Record<string, string>>>({});
  const [executing, setExecuting] = useState<string | null>(null);

  useEffect(() => {
    const loadIncidents = async () => {
      const data = await fetchWithFallback('/incidents', []);
      // Filter to only show open/active incidents
      const activeIncidents = data.filter((inc: any) =>
        inc.status === 'open' || inc.status === 'acknowledged' || inc.status === 'investigating'
      );
      setIncidents(activeIncidents);
      setLoading(false);
    };
    loadIncidents();
  }, []);

  const handleInputChange = (key: string, paramName: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [key]: {
        ...prev[key],
        [paramName]: value,
      },
    }));
  };

  const handleExecute = async (incidentId: string, actionId: string, service: string) => {
    const formKey = `${incidentId}-${actionId}`;
    const params = formData[formKey] || {};

    const payload = {
      service: service,
      parameters: { ...params },
      incident_id: incidentId,
    };

    setExecuting(formKey);

    try {
      const result = await postWithFallback(`/autoheal/${actionId}`, payload, {
        success: true,
        dry_run: true,
        message: `[DRY RUN] Would execute ${autohealActions[actionId as keyof typeof autohealActions]?.name}`
      });

      toast({
        title: result.dry_run ? 'Dry Run Complete' : 'Action Executed',
        description: result.message || 'Action completed successfully',
        variant: result.success ? 'default' : 'destructive',
      });
    } catch (error) {
      toast({
        title: 'Execution Failed',
        description: 'Failed to execute autoheal action',
        variant: 'destructive',
      });
    } finally {
      setExecuting(null);
    }
  };

  if (loading) return <TableSkeleton />;

  if (incidents.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-6"
      >
        <div>
          <h1 className="text-3xl font-bold">Autoheal Runbooks</h1>
          <p className="text-muted-foreground">Automated recovery actions for active incidents</p>
        </div>

        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="p-4 rounded-full bg-green-500/10">
              <Zap className="h-12 w-12 text-green-500" />
            </div>
            <h2 className="text-2xl font-semibold">All Clear!</h2>
            <p className="text-muted-foreground max-w-md">
              No active incidents requiring remediation. Autoheal actions will appear here when incidents are detected.
            </p>
          </div>
        </Card>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-3xl font-bold">Autoheal Runbooks</h1>
        <p className="text-muted-foreground">Automated recovery actions for active incidents</p>
        <div className="mt-2 flex items-center gap-2">
          <Badge variant="outline" className="text-yellow-600 border-yellow-600">
            Dry Run Mode
          </Badge>
          <span className="text-sm text-muted-foreground">Actions are simulated by default</span>
        </div>
      </div>

      <div className="space-y-6">
        {incidents.map((incident, index) => {
          const suggestedActions = getSuggestedActions(incident);
          const isExpanded = expandedIncident === incident.id;

          return (
            <motion.div
              key={incident.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card className="overflow-hidden">
                {/* Incident Header */}
                <div
                  className="p-6 cursor-pointer hover:bg-muted/50 transition-colors border-b"
                  onClick={() => setExpandedIncident(isExpanded ? null : incident.id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1">
                      <div className="p-3 rounded-lg bg-red-500/10">
                        <AlertTriangle className="h-6 w-6 text-red-500" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-xl font-semibold">{incident.title}</h3>
                          <Badge className={getSeverityColor(incident.severity)}>
                            {incident.severity?.toUpperCase()}
                          </Badge>
                          <Badge variant="outline">{incident.status}</Badge>
                        </div>
                        <p className="text-muted-foreground mb-2">{incident.description}</p>
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-4 w-4" />
                            {new Date(incident.created).toLocaleString()}
                          </span>
                          {incident.service && (
                            <span>Service: <strong>{incident.service}</strong></span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-muted-foreground mb-1">Suggested Actions</p>
                      <Badge variant="secondary">{suggestedActions.length} available</Badge>
                    </div>
                  </div>
                </div>

                {/* Autoheal Actions */}
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    className="bg-muted/30"
                  >
                    <div className="p-6 space-y-4">
                      <h4 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">
                        Recommended Autoheal Actions
                      </h4>
                      <div className="grid gap-3">
                        {suggestedActions.map((actionId) => {
                          const action = autohealActions[actionId as keyof typeof autohealActions];
                          if (!action) return null;

                          const Icon = action.icon;
                          const formKey = `${incident.id}-${actionId}`;
                          const isActionExpanded = expandedAction === formKey;
                          const isExecuting = executing === formKey;

                          return (
                            <Card key={actionId} className="overflow-hidden">
                              <div
                                className="p-4 cursor-pointer hover:bg-muted/50 transition-colors flex items-center justify-between"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedAction(isActionExpanded ? null : formKey);
                                }}
                              >
                                <div className="flex items-center gap-3">
                                  <div className="p-2 rounded bg-muted">
                                    <Icon className="h-5 w-5" />
                                  </div>
                                  <div>
                                    <h5 className="font-medium">{action.name}</h5>
                                    <p className="text-sm text-muted-foreground">{action.description}</p>
                                  </div>
                                </div>
                                <Button
                                  size="sm"
                                  variant={isActionExpanded ? "secondary" : "default"}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (!isActionExpanded) {
                                      setExpandedAction(formKey);
                                    } else {
                                      handleExecute(incident.id, actionId, incident.service || '');
                                    }
                                  }}
                                  disabled={isExecuting}
                                  className="gap-2"
                                >
                                  {isExecuting ? (
                                    <>
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                      Running...
                                    </>
                                  ) : isActionExpanded ? (
                                    <>
                                      <Play className="h-4 w-4" />
                                      Execute
                                    </>
                                  ) : (
                                    'Configure'
                                  )}
                                </Button>
                              </div>

                              {isActionExpanded && (
                                <div className="p-4 pt-0 border-t bg-background/50">
                                  <div className="grid gap-3 sm:grid-cols-2 mt-4">
                                    <div className="space-y-2">
                                      <Label>Target Service</Label>
                                      <Input
                                        value={incident.service || ''}
                                        disabled
                                        className="bg-muted"
                                      />
                                    </div>
                                    {action.parameters.map((param) => (
                                      <div key={param.name} className="space-y-2">
                                        <Label htmlFor={`${formKey}-${param.name}`}>
                                          {param.label}
                                        </Label>
                                        <Input
                                          id={`${formKey}-${param.name}`}
                                          type={param.type || 'text'}
                                          placeholder={param.placeholder}
                                          value={formData[formKey]?.[param.name] || param.default || ''}
                                          onChange={(e) => handleInputChange(formKey, param.name, e.target.value)}
                                          onClick={(e) => e.stopPropagation()}
                                        />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </Card>
                          );
                        })}
                      </div>
                    </div>
                  </motion.div>
                )}
              </Card>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
