import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { fetchWithFallback } from '@/lib/api';
import { TableSkeleton } from '@/components/SkeletonLoader';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { AlertCircle, Clock, User, CheckCircle2, Shield } from 'lucide-react';

interface Incident {
  id: string;
  title: string;
  severity: string;
  status: string;
  service: string;
  created: string;
  assignee: string;
  affectedUsers: number;
}

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const loadIncidents = async () => {
      // Don't use mock data - only show real incidents from API
      const data = await fetchWithFallback<Incident[]>('/incidents', []);
      // Filter to only show open incidents (not acknowledged/resolved/closed)
      const openIncidents = data.filter(i => i.status.toLowerCase() === 'open');
      setIncidents(openIncidents);
      setLoading(false);
    };
    loadIncidents();
  }, []);

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
      case 'sev1':
        return 'bg-red-500 text-white';
      case 'high':
      case 'sev2':
        return 'bg-orange-500 text-white';
      case 'medium':
      case 'sev3':
        return 'bg-yellow-500 text-white';
      default:
        return 'bg-blue-500 text-white';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return 'bg-red-500/20 text-red-500';
      case 'acknowledged':
      case 'investigating':
        return 'bg-yellow-500/20 text-yellow-500';
      case 'resolved':
        return 'bg-green-500/20 text-green-500';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  if (loading) return <TableSkeleton />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Incidents</h1>
          <p className="text-muted-foreground">Active and historical incidents</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="gap-1">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            {incidents.filter((i) => i.status.toLowerCase() === 'open').length} Open
          </Badge>
          <Badge variant="outline">
            {incidents.filter((i) => ['acknowledged', 'investigating'].includes(i.status.toLowerCase())).length} Investigating
          </Badge>
        </div>
      </div>

      {incidents.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="p-12">
            <div className="flex flex-col items-center justify-center text-center">
              <div className="h-16 w-16 rounded-full bg-green-500/10 flex items-center justify-center mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-500" />
              </div>
              <h3 className="text-xl font-semibold mb-2">All Systems Operational</h3>
              <p className="text-muted-foreground max-w-md">
                No incidents detected. Your systems are running smoothly.
                The AI monitoring will automatically create incidents when issues are detected.
              </p>
              <div className="flex items-center gap-2 mt-6 text-sm text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>Monitoring active • Checking every 5 minutes</span>
              </div>
            </div>
          </Card>
        </motion.div>
      ) : (
        <div className="grid gap-4">
          {incidents.map((incident, index) => (
            <motion.div
              key={incident.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card
                className="p-4 hover:shadow-lg transition-all cursor-pointer border-l-4"
                style={{
                  borderLeftColor: incident.severity.toLowerCase() === 'critical' ? 'rgb(239, 68, 68)' :
                    incident.severity.toLowerCase() === 'high' ? 'rgb(249, 115, 22)' :
                    incident.severity.toLowerCase() === 'medium' ? 'rgb(234, 179, 8)' : 'rgb(59, 130, 246)'
                }}
                onClick={() => navigate(`/incidents/${incident.id}`)}
              >
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 mt-1">
                    <AlertCircle className="h-5 w-5 text-muted-foreground" />
                  </div>

                  <div className="flex-1 space-y-2">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="font-semibold text-lg">{incident.title}</h3>
                        <p className="text-sm text-muted-foreground">{incident.service}</p>
                      </div>
                      <div className="flex gap-2">
                        <Badge className={getSeverityColor(incident.severity)}>
                          {incident.severity.toUpperCase()}
                        </Badge>
                        <Badge className={getStatusColor(incident.status)}>
                          {incident.status}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex items-center gap-6 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        {new Date(incident.created).toLocaleString()}
                      </div>
                      <div className="flex items-center gap-1">
                        <User className="h-4 w-4" />
                        {incident.assignee}
                      </div>
                      {incident.affectedUsers > 0 && (
                        <div className="text-red-500 font-medium">
                          {incident.affectedUsers.toLocaleString()} users affected
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
