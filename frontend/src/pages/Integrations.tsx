import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { fetchWithFallback } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { toast } from '@/hooks/use-toast';
import {
  CheckCircle,
  XCircle,
  RefreshCw,
  Slack,
  Mail,
  Bell,
  GitBranch,
  Database,
  Cloud,
  Lock,
  Trash2,
} from 'lucide-react';

interface SlackWorkspace {
  team_id: string;
  team_name: string;
  default_channel: string;
  is_active: boolean;
}

const comingSoonIntegrations = [
  { id: 'pagerduty', name: 'PagerDuty', icon: Bell, description: 'Incident alerting and on-call management' },
  { id: 'email', name: 'Email', icon: Mail, description: 'Email notifications for incidents' },
  { id: 'github', name: 'GitHub', icon: GitBranch, description: 'Link incidents to deployments and PRs' },
  { id: 'datadog', name: 'Datadog', icon: Database, description: 'Import metrics and APM data' },
  { id: 'aws', name: 'AWS CloudWatch', icon: Cloud, description: 'Monitor AWS infrastructure' },
  { id: 'okta', name: 'Okta SSO', icon: Lock, description: 'Single sign-on authentication' },
];

export default function Integrations() {
  const [slackWorkspaces, setSlackWorkspaces] = useState<SlackWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();

  // Handle OAuth callback params
  useEffect(() => {
    const slackConnected = searchParams.get('slack_connected');
    const teamName = searchParams.get('team_name');
    const slackError = searchParams.get('slack_error');

    if (slackConnected === 'true') {
      toast({
        title: 'Slack Connected!',
        description: `Successfully connected to ${teamName || 'workspace'}`,
      });
      // Clear the URL params
      setSearchParams({});
    } else if (slackError) {
      toast({
        title: 'Slack Connection Failed',
        description: slackError,
        variant: 'destructive',
      });
      setSearchParams({});
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const loadIntegrations = async () => {
      try {
        const data = await fetchWithFallback<SlackWorkspace[]>('/slack/workspaces', []);
        setSlackWorkspaces(data);
      } catch (e) {
        setSlackWorkspaces([]);
      }
      setLoading(false);
    };
    loadIntegrations();
  }, []);

  const handleConnectSlack = async () => {
    try {
      const response = await fetchWithFallback<{ install_url: string }>('/slack/install', { install_url: '' });
      if (response.install_url) {
        window.open(response.install_url, '_blank');
      } else {
        toast({
          title: 'Error',
          description: 'Could not get Slack install URL. Make sure you are logged in.',
          variant: 'destructive',
        });
      }
    } catch (e) {
      toast({
        title: 'Error',
        description: 'Failed to connect to Slack',
        variant: 'destructive',
      });
    }
  };

  const handleTestSlack = async (teamId: string) => {
    toast({
      title: 'Testing Connection',
      description: 'Sending test message to Slack...',
    });
    await fetchWithFallback(`/slack/workspaces/${teamId}/test`, { success: true }, { method: 'POST' });
  };

  const handleDisconnectSlack = async (teamId: string, teamName: string) => {
    if (!confirm(`Are you sure you want to disconnect ${teamName}?`)) {
      return;
    }

    try {
      await fetchWithFallback(`/slack/workspaces/${teamId}`, { success: true }, { method: 'DELETE' });
      toast({
        title: 'Disconnected',
        description: `Successfully disconnected from ${teamName}`,
      });
      // Remove from local state
      setSlackWorkspaces(prev => prev.filter(w => w.team_id !== teamId));
    } catch (e) {
      toast({
        title: 'Error',
        description: 'Failed to disconnect Slack workspace',
        variant: 'destructive',
      });
    }
  };

  const isSlackConnected = slackWorkspaces.length > 0 && slackWorkspaces.some(w => w.is_active);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-8"
    >
      <div>
        <h1 className="text-3xl font-bold">Integrations</h1>
        <p className="text-muted-foreground">Connect your tools and services</p>
      </div>

      {/* Active Integrations */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Available</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {/* Slack Integration */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Card className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="h-10 w-10 rounded-lg bg-[#4A154B] flex items-center justify-center">
                      <Slack className="h-6 w-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold">Slack</h3>
                      <p className="text-sm text-muted-foreground">Real-time incident alerts</p>
                    </div>
                  </div>

                  {isSlackConnected ? (
                    <div className="mt-4 space-y-2">
                      <Badge className="gap-1 bg-green-500/20 text-green-500">
                        <CheckCircle className="h-3 w-3" />
                        Connected
                      </Badge>
                      {slackWorkspaces.map(workspace => (
                        <div key={workspace.team_id} className="text-sm text-muted-foreground">
                          <span className="font-medium">{workspace.team_name || workspace.team_id}</span>
                          <span className="mx-2">•</span>
                          <span>#{workspace.default_channel}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-4">
                      <Badge variant="outline" className="gap-1">
                        <XCircle className="h-3 w-3" />
                        Not Connected
                      </Badge>
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-2">
                  {isSlackConnected ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => slackWorkspaces[0] && handleTestSlack(slackWorkspaces[0].team_id)}
                        className="gap-2"
                      >
                        <RefreshCw className="h-4 w-4" />
                        Test
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleConnectSlack}
                      >
                        Add Workspace
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => slackWorkspaces[0] && handleDisconnectSlack(
                          slackWorkspaces[0].team_id,
                          slackWorkspaces[0].team_name || slackWorkspaces[0].team_id
                        )}
                        className="gap-2"
                      >
                        <Trash2 className="h-4 w-4" />
                        Disconnect
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" onClick={handleConnectSlack}>
                      Connect
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </div>

      {/* Coming Soon */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Coming Soon</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {comingSoonIntegrations.map((integration, index) => (
            <motion.div
              key={integration.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card className="p-6 opacity-60">
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center">
                    <integration.icon className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold">{integration.name}</h3>
                      <Badge variant="outline" className="text-xs">Coming Soon</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{integration.description}</p>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
